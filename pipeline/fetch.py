from dotenv import load_dotenv
import os

load_dotenv()  # 👈 THIS LINE IS THE KEY

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

# Your fetch logic will go here
if __name__ == "__main__":
    # Verify tokens are loaded
    if GITHUB_TOKEN:
        print(f"✓ GitHub token loaded: {GITHUB_TOKEN[:6]}...")
    else:
        print("✗ GitHub token not found!")
    
    if HF_TOKEN:
        print(f"✓ HF token loaded: {HF_TOKEN[:6]}...")
    else:
        print("✗ HF token not found (optional)")

