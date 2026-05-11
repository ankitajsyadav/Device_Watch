Snapshots written by `scripts/refresh_data.py` land here.
The `device_enforcement.parquet` file is generated, not committed by default.
After running the refresh script you may want to commit it so the app
deploys to Streamlit Cloud without a fetch step.
