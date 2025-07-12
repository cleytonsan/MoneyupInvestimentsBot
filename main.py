import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Carrega variáveis de ambiente locais (caso execute localmente)
load_dotenv()

# Chaves de ambiente vindas do Railway ou .env local
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Permissões básicas do bot
intents = discord.Intents.default()
intents.message_content = True

# Inicializa o bot com prefixo !
bot = commands.Bot(command_prefix="!", intents=intents)

# Evento chamado quando o bot estiver pronto
@bot.event
async def on_ready():
    print(f"✅ Bot está online como {bot.user.name}")

# Comando simples de teste de vida
@bot.command()
async def ping(ctx):
    await ctx.send("🏓 Pong!")

# Comando para retornar parte da chave da API Alpha Vantage (teste)
@bot.command()
async def chave(ctx):
    if ALPHA_VANTAGE_API_KEY:
        await ctx.send(f"🔑 AlphaVantage Key (parcial): {ALPHA_VANTAGE_API_KEY[:4]}****")
    else:
        await ctx.send("❌ A chave da API não está configurada.")

# Comando para retornar o nome do bot
@bot.command()
async def quem(ctx):
    await ctx.send(f"🤖 Eu sou o bot {bot.user.name}, seu assistente de investimentos!")

# Comando futuro para responder com dados da Gemini (placeholder)
@bot.command()
async def cripto(ctx):
    await ctx.send("💸 Em breve: cotação de criptomoedas via Gemini API!")

# Roda o bot
if DISCORD_BOT_TOKEN:
    bot.run(DISCORD_BOT_TOKEN)
else:
    print("❌ Token do Discord não encontrado. Configure a variável DISCORD_BOT_TOKEN.")
