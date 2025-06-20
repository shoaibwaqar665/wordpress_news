# WordPress News Generator with Hugging Face API

This script generates blog posts using Hugging Face models via API and posts them to WordPress automatically.

## Changes from Gemini Version

- **Replaced Google Gemini AI** with **Hugging Face Inference API**
- **No API key required** - uses free public models
- **Better privacy** - no data sent to Google
- **Ultra lightweight** - no heavy ML libraries needed
- **Fast setup** - just requests library required

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Create .env file:**
   ```bash
   # WordPress Configuration
   WORDPRESS_USERNAME=your_wordpress_username
   WORDPRESS_PASSWORD=your_wordpress_password
   WORDPRESS_URL=https://your-wordpress-site.com
   
   # Optional: Hugging Face token (for private models)
   HUGGINGFACE_TOKEN=your_hf_token
   
   # Optional: Choose a different Hugging Face model
   HUGGINGFACE_MODEL=mistralai/Mistral-Nemo-Instruct-2407
   ```

3. **Run the script:**
   ```bash
   python main.py
   ```

## Available Models

You can change the model by setting the `HUGGINGFACE_MODEL` environment variable. Some good options:

- `mistralai/Mistral-Nemo-Instruct-2407` (default) - Lightweight, efficient Mistral model
- `microsoft/DialoGPT-medium` - Good for conversational text
- `gpt2` - Classic GPT-2 model
- `EleutherAI/gpt-neo-125M` - Smaller, faster model
- `facebook/opt-125m` - Meta's OPT model
- `microsoft/DialoGPT-large` - Larger, more capable model

## Features

- ✅ Automatic blog post generation
- ✅ SEO keyword generation
- ✅ WordPress category management
- ✅ Duplicate content detection
- ✅ HTML formatting for WordPress
- ✅ API-based execution (no local model loading)
- ✅ Ultra lightweight (only requests library)
- ✅ No GPU required

## Requirements

- Python 3.7+
- Internet connection (for API calls)
- WordPress site with REST API enabled

## Notes

- **No model download required** - uses Hugging Face Inference API
- **Free tier available** - most models are free to use
- **Fast startup** - no heavy dependencies to install
- **Rate limits may apply** - depending on model popularity
- You can get a free Hugging Face token for higher rate limits

## Additional Notes

- First run will download the model (~240MB for Mistral-Nemo-Instruct-2407)
- Generation is faster with the lightweight Mistral model
- You can adjust generation parameters in the code for different results 