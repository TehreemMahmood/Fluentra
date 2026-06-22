"""
deep_wav2vec_pipeline.py

Provides:
- DysfluencyAudioDataset, Wav2VecCollator
- Wav2VecCnnBiLstmClassifier (wav2vec2 encoder + CNN + BiLSTM head)
- Training loop with AMP, grad accumulation, checkpointing
- Inference helpers: predict_dysfluency_file
- Real-time monitor: start_realtime_dysfluency_monitor (uses sounddevice)
- Latency benchmark and simple reporting/visualization helpers

Notes:
- Requires: torch, transformers, soundfile, numpy, scikit-learn, sounddevice (optional), matplotlib (optional)
- Designed to be imported into a notebook: `from deep_wav2vec_pipeline import ...`
"""

import os
import time
import math
import json
import typing as t
from dataclasses import dataclass

import numpy as np
import soundfile as sf
import matplotlib.pyplot as plt

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torch.optim import AdamW
from torch.cuda.amp import autocast, GradScaler
import torch.nn.functional as F

from transformers import Wav2Vec2FeatureExtractor, Wav2Vec2Model
from sklearn.metrics import confusion_matrix, classification_report

# ----------------------------- Dataset & Collator -----------------------------
class DysfluencyAudioDataset(Dataset):
    def __init__(self, records: t.List[t.Tuple[str, int]], sr: int = 16000, max_duration: float = 6.0):
        """records: list of (audio_path, label)
        Loads audio on the fly; crops/pads to max_duration seconds."""
        self.records = records
        self.sr = sr
        self.max_len = int(sr * max_duration)

    def __len__(self):
        return len(self.records)

    def __getitem__(self, idx):
        path, label = self.records[idx]
        wav, sr = sf.read(path, dtype='float32')
        if wav.ndim > 1:
            wav = np.mean(wav, axis=1)
        if sr != self.sr:
            # lazy resample via numpy (falls back to caller to install librosa for better resampling)
            try:
                import librosa
                wav = librosa.resample(wav, orig_sr=sr, target_sr=self.sr)
            except Exception:
                # crude: trim or pad only
                pass
        # trim or pad
        if len(wav) > self.max_len:
            start = 0
            wav = wav[start:start + self.max_len]
        else:
            pad = self.max_len - len(wav)
            wav = np.pad(wav, (0, pad))
        return torch.from_numpy(wav).float(), int(label), os.path.basename(path)

@dataclass
class Wav2VecCollator:
    feature_extractor_name: str = 'facebook/wav2vec2-base-960h'
    feature_extractor: t.Any = None

    def __post_init__(self):
        if self.feature_extractor is None:
            self.feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(self.feature_extractor_name)

    def __call__(self, batch):
        # batch: list of (waveform_tensor, label, filename)
        wavs = [b[0].numpy() for b in batch]
        labels = torch.tensor([b[1] for b in batch], dtype=torch.long)
        filenames = [b[2] for b in batch]
        enc = self.feature_extractor(wavs, sampling_rate=self.feature_extractor.sampling_rate,
                                     return_tensors='pt', padding=True)
        input_values = enc['input_values']  # shape (batch, seq_len)
        attention_mask = enc.get('attention_mask', None)
        if attention_mask is not None:
            return input_values, attention_mask, labels, filenames
        return input_values, None, labels, filenames

# ----------------------------- Model -----------------------------
class Wav2VecCnnBiLstmClassifier(nn.Module):
    def __init__(self,
                 wav2vec_name: str = 'facebook/wav2vec2-base-960h',
                 freeze_wav2vec: bool = True,
                 cnn_channels: t.List[int] = (128, 256),
                 lstm_hidden: int = 256,
                 lstm_layers: int = 1,
                 num_classes: int = 5,
                 dropout: float = 0.3):
        super().__init__()
        self.wav2vec = Wav2Vec2Model.from_pretrained(wav2vec_name)
        if freeze_wav2vec:
            for p in self.wav2vec.parameters():
                p.requires_grad = False
        hidden_size = self.wav2vec.config.hidden_size
        # CNN layers operate on (batch, hidden, seq_len)
        convs = []
        in_ch = hidden_size
        for out_ch in cnn_channels:
            convs.append(nn.Conv1d(in_ch, out_ch, kernel_size=3, padding=1))
            convs.append(nn.BatchNorm1d(out_ch))
            convs.append(nn.ReLU())
            convs.append(nn.MaxPool1d(2))
            in_ch = out_ch
        self.cnn = nn.Sequential(*convs)  # reduces seq_len by 2^len(cnn_channels)
        self.lstm = nn.LSTM(input_size=in_ch, hidden_size=lstm_hidden, num_layers=lstm_layers,
                            batch_first=True, bidirectional=True)
        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(lstm_hidden * 2, lstm_hidden),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(lstm_hidden, num_classes)
        )

    def forward(self, input_values, attention_mask=None):
        # input_values: (batch, seq)
        outputs = self.wav2vec(input_values, attention_mask=attention_mask, return_dict=True)
        x = outputs.last_hidden_state  # (batch, seq, hidden)
        # transpose for conv: (batch, hidden, seq)
        x = x.transpose(1, 2)
        x = self.cnn(x)
        # transpose back to (batch, seq', hidden')
        x = x.transpose(1, 2)
        # LSTM
        o, _ = self.lstm(x)
        # pool across time (mean)
        pooled = o.mean(dim=1)
        logits = self.classifier(pooled)
        return logits

# ----------------------------- Training & Eval -----------------------------

def compute_class_weights(labels):
    from collections import Counter
    cnt = Counter(labels)
    total = sum(cnt.values())
    weights = {k: total / (len(cnt) * v) for k, v in cnt.items()}
    # return tensor aligned by label index
    max_label = max(cnt.keys())
    w = [weights.get(i, 1.0) for i in range(max_label + 1)]
    return torch.tensor(w, dtype=torch.float)


def train_epoch(model, dataloader, optimizer, device, scaler=None, grad_accum=1, clip_grad_norm=None):
    model.train()
    running_loss = 0.0
    it = 0
    optimizer.zero_grad()
    for step, batch in enumerate(dataloader):
        input_values, attention_mask, labels, _ = batch
        input_values = input_values.to(device)
        labels = labels.to(device)
        if attention_mask is not None:
            attention_mask = attention_mask.to(device)
        with autocast(enabled=(scaler is not None)):
            logits = model(input_values, attention_mask)
            loss = F.cross_entropy(logits, labels)
            loss = loss / grad_accum
        if scaler is not None:
            scaler.scale(loss).backward()
        else:
            loss.backward()
        if (step + 1) % grad_accum == 0:
            if scaler is not None:
                scaler.unscale_(optimizer)
                if clip_grad_norm:
                    torch.nn.utils.clip_grad_norm_(model.parameters(), clip_grad_norm)
                scaler.step(optimizer)
                scaler.update()
            else:
                if clip_grad_norm:
                    torch.nn.utils.clip_grad_norm_(model.parameters(), clip_grad_norm)
                optimizer.step()
            optimizer.zero_grad()
        running_loss += loss.item() * grad_accum
        it += 1
    return running_loss / max(it, 1)


def evaluate(model, dataloader, device):
    model.eval()
    preds = []
    trues = []
    with torch.no_grad():
        for batch in dataloader:
            input_values, attention_mask, labels, _ = batch
            input_values = input_values.to(device)
            if attention_mask is not None:
                attention_mask = attention_mask.to(device)
            logits = model(input_values, attention_mask)
            probs = F.softmax(logits, dim=-1).cpu().numpy()
            p = probs.argmax(axis=1).tolist()
            preds.extend(p)
            trues.extend(labels.numpy().tolist())
    return preds, trues


def run_training(records_train, records_val, cfg: dict):
    device = torch.device('cuda' if torch.cuda.is_available() and cfg.get('use_cuda', True) else 'cpu')
    collator = Wav2VecCollator(feature_extractor_name=cfg.get('feature_extractor_name', 'facebook/wav2vec2-base-960h'))
    train_ds = DysfluencyAudioDataset(records_train, sr=cfg.get('sr', 16000), max_duration=cfg.get('max_duration', 6.0))
    val_ds = DysfluencyAudioDataset(records_val, sr=cfg.get('sr', 16000), max_duration=cfg.get('max_duration', 6.0))
    train_loader = DataLoader(train_ds, batch_size=cfg.get('batch_size', 8), shuffle=True, collate_fn=collator)
    val_loader = DataLoader(val_ds, batch_size=cfg.get('batch_size', 8), shuffle=False, collate_fn=collator)

    model = Wav2VecCnnBiLstmClassifier(wav2vec_name=cfg.get('wav2vec_name', 'facebook/wav2vec2-base-960h'),
                                      freeze_wav2vec=cfg.get('freeze_wav2vec', True),
                                      cnn_channels=cfg.get('cnn_channels', (128, 256)),
                                      lstm_hidden=cfg.get('lstm_hidden', 256),
                                      lstm_layers=cfg.get('lstm_layers', 1),
                                      num_classes=cfg.get('num_classes', 5),
                                      dropout=cfg.get('dropout', 0.3))
    model = model.to(device)
    optimizer = AdamW(filter(lambda p: p.requires_grad, model.parameters()), lr=cfg.get('lr', 1e-4))
    scaler = GradScaler() if cfg.get('use_amp', False) and device.type == 'cuda' else None

    best_val_acc = 0.0
    epochs = cfg.get('epochs', 10)
    grad_accum = cfg.get('grad_accum', 1)
    save_dir = cfg.get('save_dir', 'saved_models')
    os.makedirs(save_dir, exist_ok=True)

    history = {'train_loss': [], 'val_acc': []}
    for epoch in range(1, epochs + 1):
        st = time.time()
        train_loss = train_epoch(model, train_loader, optimizer, device, scaler=scaler, grad_accum=grad_accum,
                                 clip_grad_norm=cfg.get('clip_grad_norm', 1.0))
        preds, trues = evaluate(model, val_loader, device)
        from sklearn.metrics import accuracy_score
        val_acc = accuracy_score(trues, preds)
        history['train_loss'].append(train_loss)
        history['val_acc'].append(val_acc)
        elapsed = time.time() - st
        print(f"Epoch {epoch}/{epochs} - loss {train_loss:.4f} - val_acc {val_acc:.4f} - {elapsed:.1f}s")
        # checkpoint
        ckpt_path = os.path.join(save_dir, f"wav2vec_epoch{epoch:02d}_acc{val_acc:.4f}.pt")
        torch.save({'model_state': model.state_dict(), 'optimizer_state': optimizer.state_dict(), 'epoch': epoch,
                    'history': history}, ckpt_path)
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_path = os.path.join(save_dir, 'best_wav2vec.pt')
            torch.save({'model_state': model.state_dict(), 'optimizer_state': optimizer.state_dict(), 'epoch': epoch,
                        'history': history}, best_path)
    return model, history

# ----------------------------- Inference Helpers -----------------------------

def predict_dysfluency_file(model,
                           audio_path: t.Union[str, np.ndarray],
                           device=None,
                           feature_extractor_name='facebook/wav2vec2-base-960h'):
    if device is None:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = model.to(device)
    model.eval()
    feat = Wav2Vec2FeatureExtractor.from_pretrained(feature_extractor_name)
    if isinstance(audio_path, np.ndarray):
        wav = audio_path.astype('float32')
        sr = feat.sampling_rate
    else:
        wav, sr = sf.read(audio_path, dtype='float32')
        if wav.ndim > 1:
            wav = np.mean(wav, axis=1)
        if sr != feat.sampling_rate:
            try:
                import librosa
                wav = librosa.resample(wav, orig_sr=sr, target_sr=feat.sampling_rate)
            except Exception:
                pass
    enc = feat(wav, sampling_rate=feat.sampling_rate, return_tensors='pt', padding=True)
    input_values = enc['input_values'].to(device)
    attention_mask = enc.get('attention_mask', None)
    if attention_mask is not None:
        attention_mask = attention_mask.to(device)
    with torch.no_grad():
        logits = model(input_values, attention_mask)
        probs = F.softmax(logits, dim=-1).cpu().numpy()[0]
    return probs

# ----------------------------- Realtime Monitor -----------------------------

def start_realtime_dysfluency_monitor(model,
                                      window_seconds: float = 2.0,
                                      hop_seconds: float = 0.5,
                                      device=None,
                                      feature_extractor_name='facebook/wav2vec2-base-960h',
                                      callback: t.Callable[[float, np.ndarray, np.ndarray], None] = None):
    """Start a streaming monitor that runs sliding-window inference. Calls `callback(t, probs, waveform)` on each window.
    Requires `sounddevice` to be installed."""
    try:
        import sounddevice as sd
    except Exception:
        raise RuntimeError('sounddevice is required for realtime monitoring')
    if device is None:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    feat = Wav2Vec2FeatureExtractor.from_pretrained(feature_extractor_name)
    sr = feat.sampling_rate
    window_samples = int(window_seconds * sr)
    buffer = np.zeros(window_samples, dtype='float32')

    def audio_callback(indata, frames, time_info, status):
        nonlocal buffer
        samples = indata[:, 0] if indata.ndim > 1 else indata
        buffer = np.concatenate([buffer[len(samples):], samples])
        # run inference on a copy to avoid blocking audio thread
        wav = buffer.copy()
        try:
            probs = predict_dysfluency_file(model, audio_path=wav, device=device, feature_extractor_name=feature_extractor_name)
        except Exception:
            # fallback: build input values manually
            try:
                enc = feat(wav, sampling_rate=sr, return_tensors='pt', padding=True)
                input_values = enc['input_values'].to(device)
                attention_mask = enc.get('attention_mask', None)
                if attention_mask is not None:
                    attention_mask = attention_mask.to(device)
                with torch.no_grad():
                    logits = model(input_values, attention_mask)
                    probs = F.softmax(logits, dim=-1).cpu().numpy()[0]
            except Exception:
                try:
                    last_layer = model.classifier[-1]
                    num_classes = int(last_layer.out_features)
                except Exception:
                    num_classes = 5
                probs = np.zeros(num_classes, dtype='float32')
        tnow = time.time()
        if callback is not None:
            callback(tnow, probs, wav)

    with sd.InputStream(samplerate=sr, channels=1, callback=audio_callback):
        print('Realtime monitor started. Press Ctrl+C to stop.')
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print('Realtime monitor stopped.')

# ----------------------------- Benchmarks & Reporting -----------------------------

def latency_benchmark(model, sample_wav: np.ndarray, iters: int = 20, device=None, feature_extractor_name='facebook/wav2vec2-base-960h'):
    if device is None:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    times = []
    for _ in range(iters):
        t0 = time.time()
        _ = predict_dysfluency_file(model, audio_path=sample_wav, device=device, feature_extractor_name=feature_extractor_name)
        times.append(time.time() - t0)
    times = np.array(times)
    return {'mean_s': times.mean(), 'p50_s': np.percentile(times, 50), 'p95_s': np.percentile(times, 95)}


def plot_confusion(trues, preds, labels: t.List[str], out_path: str = None):
    cm = confusion_matrix(trues, preds)
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
    ax.set_xticks(np.arange(len(labels)))
    ax.set_yticks(np.arange(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.set_yticklabels(labels)
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, int(cm[i, j]), ha='center', va='center', color='black')
    ax.set_ylabel('True')
    ax.set_xlabel('Pred')
    plt.tight_layout()
    if out_path:
        plt.savefig(out_path)
    return fig

# ----------------------------- Save/Load Helpers -----------------------------

def save_model_checkpoint(model, path: str):
    torch.save(model.state_dict(), path)


def load_model_from_checkpoint(path: str, cfg: dict):
    model = Wav2VecCnnBiLstmClassifier(wav2vec_name=cfg.get('wav2vec_name', 'facebook/wav2vec2-base-960h'),
                                      freeze_wav2vec=cfg.get('freeze_wav2vec', True),
                                      cnn_channels=cfg.get('cnn_channels', (128, 256)),
                                      lstm_hidden=cfg.get('lstm_hidden', 256),
                                      lstm_layers=cfg.get('lstm_layers', 1),
                                      num_classes=cfg.get('num_classes', 5),
                                      dropout=cfg.get('dropout', 0.3))
    model.load_state_dict(torch.load(path, map_location='cpu'))
    return model

# ----------------------------- Example Runner -----------------------------
if __name__ == '__main__':
    print('Module executed directly. Import the functions into your notebook.')

