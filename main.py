from dotenv import load_dotenv
load_dotenv()
import discord
from discord.ext import commands
import google.generativeai as genai
import os
import asyncio
import aiohttp
import pandas as pd
import matplotlib.pyplot as plt
import io
import re
from alpha_vantage.timeseries import TimeSeries

# --- Configurações Iniciais ---

DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
ALPHA_VANTAGE_API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY')

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

user_session_data = {}


# --- Funções Auxiliares (APIs e Geração de Gráficos) ---
async def get_selic_rate():
    try:
        url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.1178/dados/ultimos/1?formato=json"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data:
                        return data[0]['valor']
                return None
    except Exception as e:
        print(f"Erro ao buscar Selic: {e}")
        return None


async def get_ipca_rate():
    try:
        url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.13522/dados/ultimos/1?formato=json"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data:
                        return data[0]['valor']
                return None
    except Exception as e:
        print(f"Erro ao buscar IPCA: {e}")
        return None


async def get_stock_data(symbol):
    if not ALPHA_VANTAGE_API_KEY:
        print("ALPHA_VANTAGE_API_KEY não configurada.")
        return None

    try:
        ts = TimeSeries(key=ALPHA_VANTAGE_API_KEY, output_format='pandas')
        data, meta_data = await asyncio.to_thread(ts.get_daily,
                                                  symbol=symbol,
                                                  outputsize='compact')
        data.columns = [col.split('. ')[1] for col in data.columns]
        data.index = pd.to_datetime(data.index)
        data = data.sort_index()
        return data['4. close']
    except Exception as e:
        print(f"Erro ao buscar dados da ação {symbol} na Alpha Vantage: {e}")
        return None


async def generate_line_chart(data_series,
                              title="Gráfico de Preço",
                              ylabel="Preço (R$)"):
    if data_series is None or data_series.empty:
        return None

    plt.style.use('dark_background')
    plt.figure(figsize=(12, 6))
    data_series.plot(kind='line', color='cyan', marker='o', markersize=2)
    plt.xlabel("Data", color='white')
    plt.ylabel(ylabel, color='white')
    plt.title(title, color='white')
    plt.xticks(rotation=45, ha='right', color='white')
    plt.yticks(color='white')
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', transparent=True)
    buf.seek(0)
    plt.close()
    return discord.File(buf, filename="price_chart.png")


async def generate_pie_chart(allocations,
                             title="Sugestão de Alocação da Carteira"):
    if not allocations:
        return None

    labels = [f"{k} ({v:.1f}%)" for k, v in allocations.items()]
    sizes = list(allocations.values())
    colors = plt.cm.Paired(range(len(labels)))

    plt.style.use('dark_background')
    plt.figure(figsize=(10, 8))
    plt.pie(sizes,
            labels=labels,
            colors=colors,
            autopct='',
            startangle=90,
            wedgeprops={'edgecolor': 'white'})
    plt.axis('equal')
    plt.title(title, color='white')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', transparent=True)
    buf.seek(0)
    plt.close()
    return discord.File(buf, filename="allocation_chart.png")


def is_float(value):
    try:
        float(value)
        return True
    except ValueError:
        return False


# Função para dividir mensagens longas corretamente no Discord
async def send_long_message(ctx, message_content):
    max_len = 2000  # Corrigido: limite real do Discord
    if len(message_content) <= max_len:
        await ctx.send(message_content)
    else:
        parts = re.split(r'(\n---|\n## |\n### |\n#### )', message_content)
        current_part = ""
        for i, part in enumerate(parts):
            if len(current_part) + len(part) < max_len:
                current_part += part
            else:
                if current_part.strip():
                    await ctx.send(current_part.strip())
                current_part = part
        if current_part.strip():
            await ctx.send(current_part.strip())


# --- Eventos do Bot Discord ---


@bot.event
async def on_ready():
    print(f'{bot.user.name} está online!')
    print('---')


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(
            "Comando não encontrado. Use `!ajuda` para ver os comandos disponíveis."
        )
    else:
        print(f"Erro no comando: {error}")
        await ctx.send(f"Ocorreu um erro ao executar o comando: `{error}`")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    msg_content = message.content.lower()

    if "olá" in msg_content or "oi" in msg_content or "ola" in msg_content:
        if not msg_content.startswith(bot.command_prefix):
            await message.channel.send(
                f"Olá, {message.author.mention}! Sou o MoneyupInvestiments. Como posso ajudar você hoje com seus investimentos?"
            )

    if "investimento de hoje" in msg_content or "o que temos para investir" in msg_content:
        if not msg_content.startswith(bot.command_prefix):
            await message.channel.send(
                f"Para uma análise completa e sugestões de investimento, por favor, use o comando `!analisar`. Eu farei algumas perguntas para personalizar a análise."
            )

    await bot.process_commands(message)


# --- Comandos do Bot ---
@bot.command(name='analisar', help='Inicia uma análise de mercado e sugestões de investimento.')
async def analyze_investment(ctx):
    user_id = ctx.author.id
    user_session_data[user_id] = {}

    await ctx.send("Olá! Sou o MoneyupInvestiments. Vamos iniciar sua análise de investimento para este mês.")

    # 🚀 Novo passo: perguntar o perfil de investidor
    await ctx.send("Qual é o seu perfil de investidor? (Conservador, Moderado ou Agressivo)")
    try:
        profile_msg = await bot.wait_for(
            'message',
            check=lambda m: m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ['conservador', 'moderado', 'agressivo'],
            timeout=60.0
        )
        profile = profile_msg.content.lower()
        user_session_data[user_id]['profile'] = profile
        await ctx.send(f"Perfil '{profile.title()}' definido. A análise será ajustada com base nisso.")
    except asyncio.TimeoutError:
        await ctx.send("Tempo esgotado. Considerarei o perfil 'Moderado' como padrão.")
        user_session_data[user_id]['profile'] = 'moderado'

    await ctx.send("Qual o **valor total que você pretende investir este mês**? (Somente o número, ex: `1000`)")
    try:
        investment_value_msg = await bot.wait_for(
            'message',
            check=lambda m: m.author == ctx.author and m.channel == ctx.channel and is_float(m.content),
            timeout=60.0
        )
        user_session_data[user_id]['investment_value'] = float(investment_value_msg.content)
        await ctx.send(f"Ok, você pretende investir R$ {user_session_data[user_id]['investment_value']:,.2f}.")
    except asyncio.TimeoutError:
        await ctx.send("Tempo esgotado. Por favor, tente `!analisar` novamente.")
        del user_session_data[user_id]
        return

    # Busca Selic
    current_selic = await get_selic_rate()
    if not current_selic:
        await ctx.send("Não consegui buscar a **taxa Selic**. Por favor, informe (ex: `10.75`):")
        try:
            selic_msg = await bot.wait_for(
                'message',
                check=lambda m: m.author == ctx.author and m.channel == ctx.channel and is_float(m.content),
                timeout=60.0
            )
            user_session_data[user_id]['selic'] = float(selic_msg.content)
        except:
            user_session_data[user_id]['selic'] = None
    else:
        user_session_data[user_id]['selic'] = current_selic
        await ctx.send(f"A taxa Selic atual (via API) é: **{current_selic}%**.")

    # Busca IPCA
    current_ipca = await get_ipca_rate()
    if not current_ipca:
        await ctx.send("Não consegui buscar o **IPCA**. Por favor, informe (ex: `0.5`):")
        try:
            ipca_msg = await bot.wait_for(
                'message',
                check=lambda m: m.author == ctx.author and m.channel == ctx.channel and is_float(m.content),
                timeout=60.0
            )
            user_session_data[user_id]['ipca'] = float(ipca_msg.content)
        except:
            user_session_data[user_id]['ipca'] = None
    else:
        user_session_data[user_id]['ipca'] = current_ipca
        await ctx.send(f"A taxa IPCA atual (via API) é: **{current_ipca}%**.")

 

    # 📊 Perfis descritivos
    profile_description = {
        'conservador': 'baixa tolerância a risco, foco em segurança e liquidez, prioriza renda fixa e proteção do capital.',
        'moderado': 'equilíbrio entre segurança e rentabilidade, aceita riscos controlados e preza por diversificação.',
        'agressivo': 'alta tolerância a risco, busca rentabilidade elevada com exposição a renda variável e ativos voláteis.'
    }

    investment_value = user_session_data[user_id]['investment_value']
    selic_info = f"{user_session_data[user_id]['selic']}%" if user_session_data[user_id]['selic'] else "Não informada"
    ipca_info = f"{user_session_data[user_id]['ipca']}%" if user_session_data[user_id]['ipca'] else "Não informada"
    perception = user_session_data[user_id]['market_perception']
    profile_key = user_session_data[user_id]['profile']

    # 🧠 Prompt para Gemini (adaptado)
    prompt = f"""
Você é um consultor financeiro chamado MoneyupInvestiments, especializado em perfis de risco. Um usuário respondeu às perguntas e você deve gerar uma análise personalizada.

📌 **Informações:**
- Perfil de investidor: {profile_key.title()} — {profile_description[profile_key]}
- Valor a investir: R$ {investment_value:,.2f}
- Taxa Selic: {selic_info}
- IPCA: {ipca_info}
- Percepção do mercado: {perception}

📈 Gere:
1. Um resumo do cenário atual.
2. Uma sugestão de alocação de carteira, com percentuais e ativos por tipo (ex: Tesouro, CDB, ações, FIIs, cripto).
3. Justificativas para cada alocação com base no perfil.
"""

    await ctx.send("Processando sua análise... Isso pode levar alguns segundos.")

    try:
        response = await asyncio.to_thread(model.generate_content, prompt)
        analysis_text = response.text
        await send_long_message(ctx, analysis_text)
    except Exception as e:
        await ctx.send(f"Erro ao gerar a análise: {e}")

@bot.command(name='ajuda',
             help='Mostra os comandos disponíveis do MoneyupInvestiments.')
async def help_command(ctx):
    embed = discord.Embed(
        title="Bem-vindo ao MoneyupInvestiments! 💰",
        description=
        "Sou seu instrutor pessoal para te ajudar a entender e navegar no mundo dos investimentos. Aqui estão os comandos que você pode usar:",
        color=discord.Color.gold())
    embed.add_field(
        name="`!analisar`",
        value=
        "Peça uma análise de mercado e sugestões de investimento específicas.",
        inline=False)
    embed.add_field(
        name="`!conceito [termo]`",
        value=
        "Obtenha uma explicação detalhada sobre Tesouro Direto, CDB, LCI, LCA, Ações, Fundos de Investimento ou Criptomoedas.",
        inline=False)
    embed.add_field(
        name="`!grafico_acao [simbolo]`",
        value=
        "Gera um gráfico histórico de preço para um símbolo de ação (ex: `!grafico_acao IBM`).",
        inline=False)
    embed.add_field(
        name="`!limpar_dados`",
        value=
        "Limpa os dados da sua sessão atual (útil se quiser recomeçar uma análise).",
        inline=False)
    embed.add_field(name="`!ajuda`",
                    value="Mostra esta mensagem de ajuda.",
                    inline=False)
    embed.add_field(
        name="Interações Naturais (sem `!`):",
        value=
        "Você também pode tentar dizer:\n- `Olá` ou `Oi`\n- `Qual o investimento de hoje`\n- `O que temos para investir`\nPara uma conversa inicial e dicas.",
        inline=False)
    embed.set_footer(
        text=
        "Lembre-se: As sugestões são baseadas nas informações disponíveis e em modelos de IA. As decisões finais são suas!"
    )
    await ctx.send(embed=embed)


@bot.command(name='limpar_dados', help='Limpa os dados da sua sessão atual.')
async def clear_data(ctx):
    user_id = ctx.author.id
    if user_id in user_session_data:
        del user_session_data[user_id]
        await ctx.send(
            "Seus dados de sessão foram limpos. Você pode iniciar uma nova análise com `!analisar`."
        )
    else:
        await ctx.send("Não há dados de sessão para limpar.")


@bot.command(name='conceito',
             help='Explica um tipo de investimento (ex: !conceito Ações).')
async def concept(ctx, *, investment_type: str):
    investment_type = investment_type.lower().strip()
    concepts = {
        "tesouro direto":
        """**Tesouro Direto**: São títulos públicos federais federais emitidos pelo Tesouro Nacional para financiar as atividades do governo. É considerado um dos investimentos mais seguros do Brasil. Existem diferentes tipos:
        - **Tesouro Selic**: Rendimento atrelado à taxa Selic, ideal para reserva de emergência.
        - **Tesouro Prefixado**: Rentabilidade definida no momento da compra.
        - **Tesouro IPCA+**: Rentabilidade atrelada à inflação (IPCA) mais uma taxa fixa.
        """,
        "cdb":
        """**CDB (Certificado de Depósito Bancário)**: Título de renda fixa emitido por bancos para captar recursos. É como um "empréstimo" que você faz ao banco. Geralmente coberto pelo FGC (Fundo Garantidor de Créditos) até R$ 250 mil por CPF/CNPJ por instituição financeira. Pode ter rendimento prefixado, pós-fixado (atrelado ao CDI) ou híbrido.
        """,
        "lci":
        """**LCI (Letra de Crédito Imobiliário)**: Título de renda fixa emitido por bancos para financiar o setor imobiliário. Uma grande vantagem é que o rendimento da LCI é **isento de Imposto de Renda** para pessoa física. Também é coberta pelo FGC.
        """,
        "lca":
        """**LCA (Letra de Crédito do Agronegócio)**: Similar à LCI, mas os recursos são destinados a financiar o setor do agronegócio. Assim como a LCI, o rendimento da LCA é **isento de Imposto de Renda** para pessoa física e é coberta pelo FGC.
        """,
        "ações":
        """**Ações**: Representam a menor parte do capital social de uma empresa. Ao comprar uma ação, você se torna sócio da empresa e pode ganhar com a valorização do preço da ação ou com o recebimento de dividendos (parte do lucro da empresa). Envolve maior risco e volatilidade.
        """,
        "fundos de investimento":
        """**Fundos de Investimento**: São veículos financeiros coletivos onde diversos investidores aplicam seu dinheiro, que é gerido por um profissional (gestor do fundo). Existem vários tipos:
        - **Fundos de Renda Fixa**: Investem predominantemente em títulos de renda fixa.
        - **Fundos Multimercado**: Podem investir em diversas classes de ativos (renda fixa, ações, câmbio, etc.), com mais flexibilidade.
        - **Fundos de Ações**: Investem a maior parte de seus recursos em ações.
        - **Fundos Imobiliários (FIIs)**: Investem em empreendimentos imobiliários (shoppings, escritórios, galpões logísticos), pagando rendimentos periódicos aos cotistas (geralmente isentos de IR).
        """,
        "criptomoedas":
        """**Criptomoedas**: São moedas digitais descentralizadas que utilizam criptografia para garantir a segurança das transações e controlar a criação de novas unidades. As mais conhecidas são Bitcoin e Ethereum. São extremamente voláteis e não possuem regulamentação completa em muitos países, o que as torna um investimento de altíssimo risco.
        """
    }

    if investment_type in concepts:
        await ctx.send(concepts[investment_type])
    else:
        await ctx.send(
            f"Desculpe, não encontrei informações sobre '{investment_type}'. Tente um dos seguintes: Tesouro Direto, CDB, LCI, LCA, Ações, Fundos de Investimento ou Criptomoedas."
        )


@bot.command(
    name='grafico_acao',
    help=
    'Gera um gráfico histórico de preço para um símbolo de ação (ex: !grafico_acao IBM).'
)
async def stock_chart(ctx, symbol: str):
    await ctx.send(
        f"Buscando dados históricos para **{symbol.upper()}**... Isso pode levar um momento."
    )
    stock_data = await get_stock_data(symbol.upper())

    if stock_data is not None and not stock_data.empty:
        chart_file = await generate_line_chart(
            stock_data, title=f"Preço de Fechamento de {symbol.upper()}")
        if chart_file:
            await ctx.send(file=chart_file)
        else:
            await ctx.send(
                f"Não foi possível gerar o gráfico para {symbol.upper()}.")
    else:
        await ctx.send(
            f"Não foi possível obter dados para o símbolo **{symbol.upper()}**. Verifique se o símbolo está correto (ex: `IBM` para ações americanas, ou pode ser necessário adicionar `.SA` para brasileiras, como `PETR4.SA` se sua chave da Alpha Vantage suportar) ou se há um problema com a API."
        )
        await ctx.send(
            "Lembre-se que a API gratuita da Alpha Vantage tem limites de requisição (5 requisições por minuto, 500 por dia) e pode focar mais em mercados globais (EUA)."
        )


# --- Executar o Bot ---
if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN:
        print(
            "Erro: DISCORD_BOT_TOKEN não encontrado. Certifique-se de adicioná-lo nas Secrets do Replit."
        )
    elif not GEMINI_API_KEY:
        print(
            "Erro: GEMINI_API_KEY não encontrado. Certifique-se de adicioná-lo nas Secrets do Replit."
        )
    elif not ALPHA_VANTAGE_API_KEY:
        print(
            "Erro: ALPHA_VANTAGE_API_KEY não encontrado. Certifique-se de adicioná-lo nas Secrets do Replit."
        )
    else:
        bot.run(DISCORD_BOT_TOKEN)
        
