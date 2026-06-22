/* Mock Data for Speech Analysis */
const mockAnalysisData = {
    fluencyScore: 82,
    stutters: [
        { type: 'Repetition', word: 'I-I-I', timestamp: '0:02', advice: 'Try to extend the vowel sound.' },
        { type: 'Block', word: '[pause] want', timestamp: '0:05', advice: 'Use a gentle onset for the "w" sound.' },
        { type: 'Prolongation', word: 'ssssschool', timestamp: '0:12', advice: 'Monitor your airflow during the "S" sound.' }
    ],
    transcript: [
        { word: "Hello,", stutter: false },
        { word: "I-I-I", stutter: true, type: "Repetition", index: 0 },
        { word: "want", stutter: true, type: "Block", index: 1 },
        { word: "to", stutter: false },
        { word: "go", stutter: false },
        { word: "to", stutter: false },
        { word: "ssssschool", stutter: true, type: "Prolongation", index: 2 },
        { word: "today.", stutter: false }
    ],
    stats: {
        blocks: 1,
        prolongations: 1,
        repetitions: 1
    }
};

const tongueTwisters = [
    { text: "Peter Piper picked a peck of pickled peppers.", difficulty: "Medium", points: 50 },
    { text: "She sells seashells by the seashore.", difficulty: "Easy", points: 30 },
    { text: "How much wood would a woodchuck chuck if a woodchuck could chuck wood?", difficulty: "Hard", points: 100 }
];
