# Copilot Instructions for Fluentra

## Project Overview
- **Fluentra** is a Django-based web application for speech analysis and language learning.
- The project is organized into two main Django apps: `fluentra` (core config) and `main` (domain logic).
- Media (user uploads) and static files (CSS, JS, images) are separated in `media/` and `static/`.

## Key Components
- `main/models.py`: Defines core data models (users, speech sessions, analysis data).
- `main/views.py`: Contains Django views for handling web requests and API endpoints.
- `main/kie_client.py` & `main/speech_analysis.py`: Integrate external services for KIE (Knowledge Information Extraction) and speech-to-text/analysis.
- `templates/`: HTML templates for all user-facing pages, organized by feature and section.
- `static/`: Custom CSS and JS for UI/UX, with modular structure for features and components.

## Developer Workflows
- **Run server:** `python manage.py runserver`
- **Run tests:** `python manage.py test main`
- **Database migrations:**
  - Create: `python manage.py makemigrations main`
  - Apply: `python manage.py migrate`
- **Media uploads:** Saved in `media/recordings/` (ensure this directory is writable).

## Project Conventions
- All new features should be added as Django apps or in the `main/` app.
- Use Django's ORM for all database access; avoid raw SQL unless necessary.
- Static assets are referenced in templates using Django's `{% static %}` tag.
- API integrations (KIE, speech analysis) are encapsulated in dedicated modules (`kie_client.py`, `speech_analysis.py`).
- Tests for `main` go in `main/tests.py`.

## Integration Points
- External KIE and speech analysis services: see `main/kie_client.py` and `main/speech_analysis.py` for request/response patterns.
- User authentication and account flows are handled via Django's built-in auth system, with custom templates in `templates/account/`.

## Examples
- To add a new speech analysis technique:
  1. Update `main/models.py` if new data is needed.
  2. Add logic in `main/speech_analysis.py`.
  3. Expose via a view in `main/views.py` and a route in `main/urls.py`.
  4. Add a template in `templates/dashboard/` if UI is needed.

## References
- Core settings: `fluentra/settings.py`
- URL routing: `fluentra/urls.py`, `main/urls.py`
- Static/Media config: `settings.py` and `media/`, `static/` folders

---
For more details, review the code in the referenced files. When in doubt, follow Django best practices unless a project-specific pattern is documented above.
