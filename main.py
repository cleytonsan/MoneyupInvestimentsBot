import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Bot está online como {bot.user.name}")

@bot.command()
async def ping(ctx):
    await ctx.send("🏓 Pong!")

# Exemplo de comando usando a chave da API (só para teste)
@bot.command()
async def chave(ctx):
    await ctx.send(f"Chave Alpha Vantage: {ALPHA_VANTAGE_API_KEY[:4]}****")

bot.run(DISCORD_BOT_TOKEN)
