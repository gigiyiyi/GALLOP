# Deploying GALLOP On Streamlit Community Cloud

## What this deployment is good for

This deployment setup is suitable for:

- demos
- pilot testing
- UI review
- early workflow validation

This setup is not yet suitable for durable multi-user production use, because the app currently relies on:

- a local SQLite database
- local file storage for uploaded documents and source-location files

## Files to commit

Commit these files and folders to GitHub:

- `app.py`
- `db.py`
- `rules.py`
- `export_pack.py`
- `constants.py`
- `i18n.py`
- `ui/`
- `cleanup_workspace.py`
- `MVP_RETENTION_POLICY.md`
- `TERMINOLOGY.md`
- `requirements.txt`
- `.gitignore`

Do not commit:

- `gallop.db`
- `gallop.db.bak`
- `data_files/`
- `.venv/`
- `__pycache__/`

## Streamlit Community Cloud deployment steps

1. Push the code to GitHub.
2. Go to [https://share.streamlit.io/](https://share.streamlit.io/).
3. Sign in and connect your GitHub account.
4. Click `Create app`.
5. Choose:
   - repository: `gigiyiyi/GALLOP`
   - branch: your main branch
   - main file path: `app.py`
6. Open `Advanced settings`.
7. Select Python `3.12` if needed.
8. Click `Deploy`.

## What happens on first launch

The app initializes its own local SQLite database on the deployment environment.

Current behavior:

- demo users are seeded by the app
- the database starts fresh on the deployed instance
- local uploaded files from your development machine are not included

So the deployed app should be treated as a fresh environment unless you build an explicit hosted data layer later.

## Important limitation

Streamlit Community Cloud is easy to deploy, but this app currently stores working data locally.

That means:

- uploaded files are not a robust long-term storage solution
- SQLite is not the right long-term shared backend for production workflow
- resets/redeployments may affect local app state

## Recommended next step for real deployment

If GALLOP moves beyond demo/pilot use, the app should be upgraded to use:

- a hosted database instead of local `gallop.db`
- object storage instead of local `data_files/`

That would make uploaded evidence, source-location files, and package metadata much safer and more stable.
