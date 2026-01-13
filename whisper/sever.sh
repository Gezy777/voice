cd /home/zxk/voice/voice/whisper
conda activate megatron
uvicorn server:app --host 0.0.0.0 --port 8000