#!/bin/bash
echo "🤖 Railway Fix Script"
echo "===================="

# Show files
echo "📁 Files in directory:"
ls -la

# Create file if doesn't exist
if [ ! -f "Anon-chat.py" ]; then
    echo "📝 Creating Anon-chat.py..."
    cat > Anon-chat.py << 'EOF'
#!/usr/bin/env python3
print("🤖 Telegram Bot Starting...")
import os
from telegram.ext import Application, CommandHandler, MessageHandler, filters

TOKEN = os.environ.get("BOT_TOKEN", "")
if not TOKEN:
    print("❌ No BOT_TOKEN!")
    exit(1)

async def start(update, context):
    await update.message.reply_text("✅ Bot is working on Railway!")

async def echo(update, context):
    await update.message.reply_text(f"You: {update.message.text}")

print("🚀 Starting bot...")
app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
print("✅ Bot is running!")
app.run_polling()
EOF
    echo "✅ Anon-chat.py created"
fi

# Make it executable
chmod +x Anon-chat.py

# Run the bot
echo "🚀 Starting bot..."
python Anon-chat.py
