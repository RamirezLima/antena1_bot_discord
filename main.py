import discord
from discord.ext import commands
import asyncio
from flask import Flask
import os
from threading import Thread
from dotenv import load_dotenv
from broadcast import EstacaoCompartilhada
from agora import Acompanhante

load_dotenv()

# Servidor Web para manter o serviço ativo
SITE_ANTENA1 = 'https://www.antena1.com.br/'
REDIRECIONAR_EM = 10  # segundos

PAGINA_STATUS = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="{REDIRECIONAR_EM};url={SITE_ANTENA1}">
  <title>Antena 1 Bot</title>
  <style>
    body {{ margin: 0; min-height: 100vh; display: grid; place-items: center; text-align: center;
           font-family: system-ui, sans-serif; background: #2755a4; color: #fff; }}
    main {{ padding: 24px; }}
    h1 {{ margin: 0 0 8px; }}
    p {{ margin: 8px 0; opacity: .9; }}
    a {{ color: #fff; font-weight: 600; }}
  </style>
</head>
<body>
  <main>
    <h1>📻 Bot online!</h1>
    <p>Você será redirecionado para a Antena 1 em <strong id="contador">{REDIRECIONAR_EM}</strong> segundos.</p>
    <p><a href="{SITE_ANTENA1}">Ir agora</a></p>
  </main>
  <script>
    let restante = {REDIRECIONAR_EM};
    const contador = document.getElementById('contador');
    setInterval(() => {{
      restante = Math.max(restante - 1, 0);
      contador.textContent = restante;
      if (restante === 0) window.location.href = "{SITE_ANTENA1}";
    }}, 1000);
  </script>
</body>
</html>"""

app = Flask('')
@app.route('/')
def home():
    return PAGINA_STATUS

def run():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 3000)))

# Inicia o servidor web em uma linha separada antes do bot
Thread(target=run).start()

# Lê o token das variáveis de ambiente (nunca fica no código)
TOKEN = os.getenv('TOKEN')
COR = discord.Color.from_str('#2755a4')
IMG = 'https://a1media.antena1.com.br/image/streams/400x400/'

# Estações públicas listadas no player de https://www.antena1.com.br/ouvir-radio-online
# (somente as que têm URL de áudio acessível; validado com ffprobe).
# A URL de cada estação vem da variável de ambiente indicada em 'env'; se ela não existir
# (ou estiver vazia), usa o valor 'padrao'.
ESTACOES = [
    {'nome': 'Normal', 'meta_id': 'antena_1', 'emoji': '📻', 'imagem': IMG + 'antena1-online.png',
     'env': 'URL-ANTENA1', 'padrao': 'https://www.antena1.com.br/stream/stream/1;',
     'descricao': 'Os grandes sucessos das paradas americanas e europeias.'},
    {'nome': 'Baixo', 'meta_id': 'antena_1', 'emoji': '📶', 'imagem': IMG + 'antena1-baixo.png',
     'env': 'URL-ANTENA1-BAIXO', 'padrao': 'https://stream.antena1.com.br/stream19',
     'descricao': 'Mesma programação, leve para internet lenta.'},
    {'nome': 'HD', 'meta_id': 'antena_1', 'emoji': '💎', 'imagem': IMG + 'antena1-hd.png',
     'env': 'URL-ANTENA1-HD', 'padrao': 'https://stream.antena1.com.br/stream20',
     'descricao': 'A programação Antena 1 na melhor qualidade de áudio.'},
    {'nome': 'Espacial', 'meta_id': 'antena_1_espacial', 'emoji': '🚀', 'imagem': IMG + 'espacial.jpg',
     'env': 'URL-ANTENA1-ESPACIAL', 'padrao': 'https://streams.radiomast.io/7c9dfc6c-917a-4500-8496-d687128c23b5',
     'descricao': 'Os grandes sucessos internacionais em uma estação à parte.'},
]
for _e in ESTACOES:
    _e['url'] = os.getenv(_e['env']) or _e['padrao']

# Uma única conexão/FFmpeg por estação, compartilhada entre todos os servidores que estiverem ouvindo
for _e in ESTACOES:
    _e['fonte'] = EstacaoCompartilhada(_e['nome'], _e['url'])

# Uma única consulta de "música atual" por metaId (Normal, Baixo e HD compartilham o mesmo),
# e somente enquanto houver algum painel ouvindo
ACOMPANHANTES = {m: Acompanhante(m) for m in {e['meta_id'] for e in ESTACOES}}


def embed_lista():
    embed = discord.Embed(title='📻 Estações da Antena 1', color=COR,
                          description='Escolha uma estação no menu abaixo, ou use `/antena 2` (ou `!antena 2`).')
    for i, e in enumerate(ESTACOES, start=1):
        embed.add_field(name=f"{i}. {e['emoji']} {e['nome']}", value=e['descricao'], inline=False)
    embed.set_thumbnail(url=ESTACOES[0]['imagem'])
    return embed


def embed_tocando(estacao, pausado=False, musica=None):
    estado = '⏸️ Pausado' if pausado else '▶️ Tocando agora'
    if musica:
        embed = discord.Embed(title=musica.titulo, color=COR)
        descricao = f"**{musica.artista}**"
        detalhes = ' • '.join(filter(None, [musica.album, str(musica.ano) if musica.ano else None]))
        if detalhes:
            descricao += f"\n{detalhes}"
        embed.description = descricao
        embed.set_author(name=f"Antena 1 • {estacao['nome']}", icon_url=estacao['imagem'])
        embed.set_thumbnail(url=musica.capa or estacao['imagem'])
    else:
        embed = discord.Embed(title=f"{estacao['emoji']} Antena 1 • {estacao['nome']}", color=COR,
                              description=estacao['descricao'])
        embed.set_thumbnail(url=estacao['imagem'])
    embed.set_footer(text=f'{estado} • /antenas para trocar de estação')
    return embed


class SelectEstacao(discord.ui.Select):
    def __init__(self, atual=None):
        opcoes = [
            discord.SelectOption(label=e['nome'], value=str(i), description=e['descricao'][:100],
                                 emoji=e['emoji'], default=(i == atual))
            for i, e in enumerate(ESTACOES)
        ]
        super().__init__(placeholder='Escolha uma estação…', options=opcoes, row=0)

    async def callback(self, interaction: discord.Interaction):
        await self.view.cog.trocar(interaction, int(self.values[0]))


class PainelView(discord.ui.View):
    """Menu de estações + botões de controle. O painel de uma estação também mostra a música atual."""

    def __init__(self, cog, atual=None, guild_id=None):
        # O painel de reprodução vive enquanto o bot estiver no canal (é encerrado ao sair); a lista expira
        super().__init__(timeout=None if atual is not None else 900)
        self.cog = cog
        self.message = None
        self.atual = atual
        self.guild_id = guild_id
        self.musica = None
        self.pausado = False
        self._token = None
        self.add_item(SelectEstacao(atual))
        if atual is None:  # lista (!antenas): só o menu
            self.remove_item(self.pausar)
            self.remove_item(self.parar)

    # --- acompanhamento da música atual (uma consulta compartilhada por metaId) ---
    def acompanhar(self):
        if self._token is None and self.atual is not None:
            self._token = ACOMPANHANTES[ESTACOES[self.atual]['meta_id']].inscrever(self.musica_mudou)

    def parar_acompanhar(self):
        if self._token is not None:
            ACOMPANHANTES[ESTACOES[self.atual]['meta_id']].desinscrever(self._token)
            self._token = None

    def embed(self):
        return embed_tocando(ESTACOES[self.atual], self.pausado, self.musica)

    async def musica_mudou(self, musica):
        self.musica = musica
        await self.atualizar()

    async def atualizar(self):
        """Edita a mensagem pelo canal (token do bot): o token da interação expira em 15 minutos."""
        if not self.message:
            return
        try:
            await self.message.edit(embed=self.embed(), view=self)
        except (discord.NotFound, discord.Forbidden):
            self.parar_acompanhar()  # mensagem apagada ou sem permissão: para de acompanhar
            self.cog.esquecer_painel(self)
        except discord.HTTPException as e:
            print(f'[painel {self.guild_id}] erro ao atualizar: {e!r}')

    def definir_pausa(self, pausado):
        """Pausado não consome a API: só acompanha a música enquanto está tocando."""
        self.pausado = pausado
        self.pausar.label, self.pausar.emoji = ('Retomar', '▶️') if pausado else ('Pausar', '⏸️')
        if pausado:
            self.parar_acompanhar()
        else:
            self.acompanhar()

    async def encerrar(self, embed=None):
        self.parar_acompanhar()
        for item in self.children:
            item.disabled = True
        self.stop()
        if self.message:
            embed = embed or discord.Embed(title='⏹️ Reprodução encerrada', color=discord.Color.dark_grey(),
                                           description='Use `/antenas` para ouvir de novo.')
            try:
                await self.message.edit(embed=embed, view=self)
            except discord.HTTPException:
                pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        vc = interaction.guild.voice_client if interaction.guild else None
        voz = getattr(interaction.user, 'voice', None)
        if self.atual is not None and (not vc or not voz or voz.channel != vc.channel):
            await interaction.response.send_message('Entre no mesmo canal de voz do bot para usar os controles.', ephemeral=True)
            return False
        return True

    @discord.ui.button(label='Pausar', emoji='⏸️', style=discord.ButtonStyle.primary, row=1)
    async def pausar(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc.is_playing():
            vc.pause()
            self.definir_pausa(True)
        elif vc.is_paused():
            vc.resume()
            self.definir_pausa(False)
        else:
            await interaction.response.send_message('Não há nada tocando.', ephemeral=True)
            return
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label='Parar', emoji='⏹️', style=discord.ButtonStyle.danger, row=1)
    async def parar(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.cog.esquecer_painel(self)
        self.parar_acompanhar()
        await interaction.guild.voice_client.disconnect()
        for item in self.children:
            item.disabled = True
        embed = discord.Embed(title='⏹️ Reprodução encerrada', color=discord.Color.dark_grey(),
                              description='Use `/antenas` para ouvir de novo.')
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix='!', intents=intents)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.monitores = {}  # guild.id -> task que desconecta o bot se o canal ficar vazio
        self.paineis = {}    # guild.id -> PainelView que está mostrando a música atual

    async def check_voice_channel(self, guild, canal_texto):
        """Monitora o canal de voz e desconecta o bot se estiver sozinho."""
        await self.bot.wait_until_ready()
        voice_client = guild.voice_client

        while voice_client and voice_client.is_connected():
            channel = voice_client.channel
            members = channel.members
            non_bot_members = [member for member in members if not member.bot]

            if len(non_bot_members) == 0:
                await canal_texto.send("Estou sozinho no canal. Desconectando...")
                await voice_client.disconnect()
                break

            await asyncio.sleep(30)

    async def iniciar(self, guild, member, canal_texto, indice):
        """Conecta no canal de voz do membro e toca a estação. Retorna uma mensagem de erro ou None."""
        if not member.voice:
            return "Você precisa estar em um canal de voz para usar este comando!"

        canal = member.voice.channel
        vc = guild.voice_client
        if vc and vc.channel != canal:
            if vc.is_playing() or vc.is_paused():
                return f"Já estou tocando no canal **{vc.channel.name}**. Entre nele para trocar a estação, ou use `/parar` para me liberar."
            await vc.move_to(canal)  # conectado mas sem tocar: acompanha quem chamou
        elif not vc:
            await canal.connect()

        vc = guild.voice_client
        if vc.is_playing() or vc.is_paused():
            vc.stop()

        vc.play(ESTACOES[indice]['fonte'].assinar(), after=lambda e: print(f'Erro: {e}') if e else None)

        monitor = self.monitores.get(guild.id)
        if not monitor or monitor.done():
            self.monitores[guild.id] = self.bot.loop.create_task(self.check_voice_channel(guild, canal_texto))
        return None

    async def mostrar_painel(self, guild, canal, indice, enviar):
        """Envia (ou edita) a mensagem com o painel da estação e passa a acompanhar a música atual."""
        view = PainelView(self, atual=indice, guild_id=guild.id)
        mensagem = await enviar(embed=embed_tocando(ESTACOES[indice]), view=view)
        view.message = canal.get_partial_message(mensagem.id) if hasattr(canal, 'get_partial_message') else mensagem

        # Inscreve o novo painel antes de soltar o anterior: se for o mesmo metaId (ex.: Normal -> HD),
        # a consulta em andamento é reaproveitada, sem nova requisição
        anterior = self.paineis.get(guild.id)
        self.paineis[guild.id] = view
        view.acompanhar()
        if anterior:
            anterior.parar_acompanhar()
            if anterior.message and anterior.message.id != view.message.id:
                await anterior.encerrar(embed=discord.Embed(title='🔁 Substituído', color=discord.Color.dark_grey(),
                                                            description='Há um painel mais recente neste servidor.'))

    def esquecer_painel(self, view):
        if self.paineis.get(view.guild_id) is view:
            del self.paineis[view.guild_id]

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Quando o bot sai do canal (por qualquer caminho), encerra o painel e a consulta da música."""
        if member.id == self.bot.user.id and before.channel and not after.channel:
            view = self.paineis.pop(member.guild.id, None)
            if view:
                await view.encerrar()

    async def trocar(self, interaction, indice):
        """Escolha no menu suspenso: toca a estação e transforma a mensagem no painel de controle."""
        await interaction.response.defer()
        erro = await self.iniciar(interaction.guild, interaction.user, interaction.channel, indice)
        if erro:
            await interaction.followup.send(erro, ephemeral=True)
            return
        await self.mostrar_painel(interaction.guild, interaction.channel, indice, interaction.edit_original_response)

    @commands.hybrid_command(description='Testa se o bot está online')
    async def ping(self, ctx):
        await ctx.send('Pong')

    @commands.hybrid_command(name='antenas', description='Lista as estações da Antena 1')
    async def antenas(self, ctx):
        view = PainelView(self)
        view.message = await ctx.send(embed=embed_lista(), view=view)

    @commands.hybrid_command(name='antena', description='Toca uma estação pelo número da lista (veja /antenas)')
    @discord.app_commands.describe(numero='Número da estação (1 a 4)')
    async def antena(self, ctx, numero: int = None):
        if numero is None or not 1 <= numero <= len(ESTACOES):
            await ctx.send(f"Informe um número de 1 a {len(ESTACOES)}. Veja a lista com `/antenas`.", ephemeral=True)
            return
        await ctx.defer()
        erro = await self.iniciar(ctx.guild, ctx.author, ctx.channel, numero - 1)
        if erro:
            await ctx.send(erro, ephemeral=True)
            return
        await self.mostrar_painel(ctx.guild, ctx.channel, numero - 1, ctx.send)

    @antena.error
    async def antena_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send("Use um número da lista. Veja com `/antenas`.")
        else:
            raise error

    @commands.hybrid_command(name='antena1', description='Toca a Antena 1 (estação Normal)')
    async def antena1(self, ctx):
        await ctx.defer()
        erro = await self.iniciar(ctx.guild, ctx.author, ctx.channel, 0)
        if erro:
            await ctx.send(erro, ephemeral=True)
            return
        await self.mostrar_painel(ctx.guild, ctx.channel, 0, ctx.send)

    @commands.hybrid_command(description='Para de tocar e desconecta')
    async def parar(self, ctx):
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send(embed=discord.Embed(title='⏹️ Desconectado!', color=discord.Color.dark_grey()))
        else:
            await ctx.send("Não estou conectado a nenhum canal de voz.", ephemeral=True)

    @commands.hybrid_command(description='Pausa a reprodução')
    async def pausar(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            view = self.paineis.get(ctx.guild.id)
            if view:
                view.definir_pausa(True)
                await view.atualizar()
            await ctx.send("⏸️ Pausado.")
        else:
            await ctx.send("Não há música sendo reproduzida.", ephemeral=True)

    @commands.hybrid_command(description='Retoma a reprodução')
    async def resumir(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            view = self.paineis.get(ctx.guild.id)
            if view:
                view.definir_pausa(False)
                await view.atualizar()
            await ctx.send("▶️ Retomado.")
        else:
            await ctx.send("Não há música pausada.", ephemeral=True)

async def setup_hook():
    # Registra o Cog uma única vez e publica os slash commands no Discord
    await bot.add_cog(Music(bot))
    await bot.tree.sync()

bot.setup_hook = setup_hook

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')

if __name__ == '__main__':
    bot.run(TOKEN)
