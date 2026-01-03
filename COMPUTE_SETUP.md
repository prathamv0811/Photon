# Compute Setup Guide (Nvidia Brev)

This guide provides the exact steps to set up your remote Nvidia Brev instance for training with Photon. Follow these steps to ensure a smooth installation and avoid permission errors.

## 1. Initial Connection

Connect to your Brev instance via your terminal:

```bash
brev shell <your-machine-name>
```

## 2. Fix Permissions (Crucial Step)

Before installing anything, ensure you own the cache directories. This prevents `Permission denied` errors during installation.

Run these commands:

```bash
# Fix ownership of the default cache directory
sudo chown -R $USER ~/.cache

# Fix ownership of the ephemeral pip cache (common on Brev)
if [ -d "/ephemeral/cache" ]; then
    sudo chown -R $USER /ephemeral/cache
fi
```

## 3. Clone Repository

```bash
git clone https://github.com/prathamv0811/Photon.git
cd Photon
```

## 4. Environment Setup & Installation

**ALWAYS** use a virtual environment. Never install directly to the system python.

```bash
# 1. Create a virtual environment
python3 -m venv .venv

# 2. Activate the environment
source .venv/bin/activate

# 3. Upgrade pip (optional but recommended)
pip install --upgrade pip

# 4. Install Photon in editable mode
pip install -e .
```

> **Note:** If you see "Permission denied" errors here, verify you ran the permission fix in Step 2 and that your virtual environment is active (you should see `(.venv)` in your prompt).

## 5. Start Training

Once installed, you can start the training process:

```bash
photon train
```

---

## Quick Troubleshooting script

You can copy and run this entire block to set everything up at once:

```bash
# 1. Fix Permissions
sudo chown -R $USER ~/.cache
[ -d "/ephemeral/cache" ] && sudo chown -R $USER /ephemeral/cache

# 2. Setup Repo
git clone https://github.com/prathamv0811/Photon.git
cd Photon

# 3. Setup Venv & Install
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# 4. Success message
echo "✅ Setup Complete! Run 'photon train' to start."
```

## Troubleshooting: Clean Re-install

If you see `Permission denied` errors (like `__init__.py`) during installation, your virtual environment is likely corrupted with root-owned files.

**Fix it by deleting and re-creating the environment:**

```bash
# 1. Deactivate current environment
deactivate 2>/dev/null

# 2. Delete the broken .venv and cache
sudo rm -rf .venv
sudo rm -rf ~/.cache/uv
sudo chown -R $USER ~/.cache

# 3. Create fresh venv (WITHOUT SUDO)
python3 -m venv .venv
source .venv/bin/activate

# 4. Install again
pip install -e .
```
