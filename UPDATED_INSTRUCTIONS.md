# ⚠️ UPDATED DEPLOYMENT INSTRUCTIONS

**IMPORTANT**: Streamlit is a Docker template, not a separate SDK on HF Spaces!

---

## ✅ CORRECT SPACE SETUP

### Step 1: Select SDK
1. Go to https://huggingface.co/spaces
2. Click "Create new Space"
3. **Select SDK: Docker** ⭐

### Step 2: Select Template
4. **Select Template: Streamlit** (second option in first row) ⭐

### Step 3: Configure Space
5. Space name: `attribution-graph-probing`
6. License: `GPL-3.0`
7. Hardware: **CPU basic** (free)
8. Visibility: **Public**
9. Click **"Create Space"**

---

## 📦 NEW FILE CREATED

**Dockerfile** - Required for Docker SDK deployment

This file tells HF Spaces how to build and run your Streamlit app.

---

## 📋 FILES TO UPLOAD (UPDATED)

### Essential Files

```
├── README.md                     (rename from README_HF.md)
├── Dockerfile                    ⭐ NEW - Required!
├── app_hf.py
├── requirements.txt              (rename from requirements_hf.txt)
├── .streamlit/config.toml
├── .gitattributes
├── eda/                          (entire directory)
├── scripts/                      (entire directory)
├── examples_data/                (entire directory)
└── LICENSE
```

---

## 🔄 WHAT CHANGED

### Before (Incorrect)
- SDK: Streamlit ❌ (doesn't exist as separate SDK)

### Now (Correct)
- SDK: Docker ✅
- Template: Streamlit ✅
- Requires: Dockerfile ✅

---

## 📝 UPDATED README_HF.md

The metadata now correctly shows:
```yaml
---
title: Attribution Graph Probing
emoji: 🔬
sdk: docker        # Changed from 'streamlit'
app_port: 7860     # Added for Docker
license: gpl-3.0
---
```

---

## 🚀 DEPLOYMENT PROCESS (NO CHANGE)

The deployment process is **exactly the same**:

1. Create Space with **Docker SDK** + **Streamlit template**
2. Upload all files (including new `Dockerfile`)
3. Wait for build
4. Test with Dallas example

---

## ✅ DOCKERFILE EXPLAINED

```dockerfile
FROM python:3.10-slim              # Base Python image
WORKDIR /app                       # Set working directory
COPY requirements.txt .            # Copy dependencies
RUN pip install -r requirements.txt # Install packages
COPY . .                           # Copy all files
EXPOSE 7860                        # Streamlit port
CMD streamlit run app_hf.py        # Run the app
```

This is **automatically handled** - you just upload it!

---

## 💡 WHY DOCKER?

Docker SDK on HF Spaces provides:
- ✅ More control over environment
- ✅ Better dependency management
- ✅ Same functionality as native Streamlit
- ✅ More flexibility for future updates

Your app works **exactly the same**!

---

## 🎯 QUICK CHECKLIST

Before uploading:
- [x] Dockerfile created ✅
- [x] README_HF.md updated (metadata changed to docker) ✅
- [ ] Select Docker SDK (not Streamlit)
- [ ] Select Streamlit template (under Docker)
- [ ] Upload Dockerfile along with other files

---

## 📚 ALL GUIDES STILL VALID

All previous guides still work, just remember:
1. Select **Docker SDK**
2. Select **Streamlit template**
3. Upload **Dockerfile** (new file)

Everything else is identical!

---

## ⚠️ COMMON MISTAKES

**Wrong**:
- Looking for "Streamlit" in SDK list ❌
- Skipping Dockerfile ❌

**Correct**:
- Select "Docker" SDK ✅
- Select "Streamlit" template ✅
- Include Dockerfile ✅

---

**Status**: ✅ UPDATED & READY

Follow the updated instructions and you're good to go! 🚀

