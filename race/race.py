# Developed by Redjumpman for Redbot.
# Inspired by the snail race mini game.

# Standard Library
import asyncio
import random
from typing import Literal

# Red
from redbot.core import Config, bank, commands, checks
from redbot.core.utils import AsyncIter
from redbot.core.errors import BalanceTooHigh

# Discord
import discord

# Race
from .animals import Animal, racers

__author__ = "Redjumpman"
__version__ = "2.1.3"


class FancyDict(dict):
    def __missing__(self, key):
        value = self[key] = type(self)()
        return value


class FancyDictList(dict):
    def __missing__(self, key):
        value = self[key] = []
        return value


class Race(commands.Cog):
    """Cog for racing animals"""

    def __init__(self):
        self.config = Config.get_conf(self, 5074395009, force_registration=True)

        self.active = FancyDict()
        self.started = FancyDict()
        self.winners = FancyDictList()
        self.players = FancyDictList()
        self.bets = FancyDict()

        guild_defaults = {
            "Wait": 60,
            "Mode": "normal",
            "Prize": 100,
            "Pooling": False,
            "Payout_Min": 0,
            "Bet_Multiplier": 2,
            "Bet_Min": 10,
            "Bet_Max": 50,
            "Bet_Allowed": True,
            "Games_Played": 0,
        }

        # First, Second, and Third place wins
        member_defaults = {"Wins": {"1": 0, "2": 0, "3": 0}, "Losses": 0}
        
        self.config.register_guild(**guild_defaults)
        self.config.register_member(**member_defaults)

    async def red_delete_data_for_user(
        self, *, requester: Literal["discord", "owner", "user", "user_strict"], user_id: int
    ):
        all_members = await self.config.all_members()
        async for guild_id, guild_data in AsyncIter(all_members.items(), steps=100):
            if user_id in guild_data:
                await self.config.member_from_ids(guild_id, user_id).clear()

    @commands.group()
    @commands.guild_only()
    async def race(self, ctx):
        """Race related commands."""
        pass

    @race.command()
    async def start(self, ctx):
        """Memulai balapan baru.

        Kamu tidak dapat membuat balapan baru saat balapan telah dimulai.

        Apabila hanya kamu yang bermain, kamu akan bermain dengan bot.

        Member yang memulai balapan secara otomatis mengikuti balapan.
        """
        if self.active[ctx.guild.id]:
            return await ctx.send(f"Perlombaan sedang berlangsung!  Ketik `{ctx.prefix}race enter` untuk bergabung!")
        self.active[ctx.guild.id] = True
        self.players[ctx.guild.id].append(ctx.author)
        wait = await self.config.guild(ctx.guild).Wait()
        current = await self.config.guild(ctx.guild).Games_Played()
        await self.config.guild(ctx.guild).Games_Played.set(current + 1)
        await ctx.send(
            f"🚩 Balapan dimulai! Ketik {ctx.prefix}race enter "
            f"untuk bergabung balapan! 🚩\nBalapan akan berlangsung dalam "
            f"{wait} detik!\n\n**{ctx.author.mention}** bergabung dalam balapan!"
        )
        await asyncio.sleep(wait)
        self.started[ctx.guild.id] = True
        await ctx.send("🏁 Perlombaan sekarang sedang berlangsung. 🏁")
        await self.run_game(ctx)

        settings = await self.config.guild(ctx.guild).all()
        currency = await bank.get_currency_name(ctx.guild)
        color = await ctx.embed_colour()
        msg, embed = await self._build_end_screen(ctx, settings, currency, color)
        await ctx.send(content=msg, embed=embed)
        await self._race_teardown(ctx, settings)

    @race.command()
    async def stats(self, ctx, user: discord.Member = None):
        """Menampilkan data balapan."""
        if not user:
            user = ctx.author
        color = await ctx.embed_colour()
        user_data = await self.config.member(user).all()
        player_total = sum(user_data["Wins"].values()) + user_data["Losses"]
        server_total = await self.config.guild(ctx.guild).Games_Played()
        try:
            percent = round((player_total / server_total) * 100, 1)
        except ZeroDivisionError:
            percent = 0
        embed = discord.Embed(color=color, description="Race Stats")
        embed.set_author(name=f"{user}", icon_url=user.avatar_url)
        embed.add_field(
            name="Menang",
            value=(
                f"1st: {user_data['Wins']['1']}\n2nd: {user_data['Wins']['2']}\n3rd: {user_data['Wins']['3']}"
            ),
        )
        embed.add_field(name="Kalah", value=f'{user_data["Losses"]}')
        embed.set_footer(
            text=(
                f"Anda telah bermain {player_total} ({percent}%) balapan "
                f"dari {server_total} total balapan di server ini."
            )
        )
        await ctx.send(embed=embed)

    @race.command()
    async def bet(self, ctx, bet: int, user: discord.Member):
        """Taruhan balapan."""
        if await self.bet_conditions(ctx, bet, user):
            self.bets[ctx.guild.id][ctx.author.id] = {user.id: bet}
            currency = await bank.get_currency_name(ctx.guild)
            await bank.withdraw_credits(ctx.author, bet)
            await ctx.send(f"{ctx.author.mention} menaruh sebanyak {bet} {currency} bertaruh untuk {user.display_name}.")

    @race.command()
    async def enter(self, ctx):
        """Begabung dalam balapan.

        Perintah ini akan menghilang sendiri saat balapan dimulai.
        Dengan tidak berulang kali memberitahukan kepada player bahwa dia mengikuti balapan.

        """
        if self.started[ctx.guild.id]:
            return await ctx.send(
                "Perlombaan telah dimulai.  Silahkan tunggu sampai itu selesai dan baru membuat perlombaan baru!."
            )
        elif not self.active.get(ctx.guild.id):
            return await ctx.send("Perlombaan harus dibuat sebelum kamu dapat bergabung.")
        elif ctx.author in self.players[ctx.guild.id]:
            return await ctx.send("Kamu telah bergabung dalam perlombaan.")
        elif len(self.players[ctx.guild.id]) >= 14:
            return await ctx.send("Jumlah maksimum peserta telah mencapai batas maksimum.")
        else:
            self.players[ctx.guild.id].append(ctx.author)
            await ctx.send(f"{ctx.author.mention} telah gabung dalam balapan.")

    @race.command(hidden=True)
    @checks.admin_or_permissions(administrator=True)
    async def clear(self, ctx):
        """ONLY USE THIS COMMAND FOR DEBUG PURPOSES

        You shouldn't use this command unless the race is stuck
        or you are debugging."""
        self.clear_local(ctx)
        await ctx.send("Race cleared.")

    @race.command()
    @checks.admin_or_permissions(administrator=True)
    async def wipe(self, ctx):
        """This command will wipe ALL race data.

        You are given a confirmation dialog when using this command.
        If you decide to wipe your data, all stats and settings will be deleted.
        """
        await ctx.send(
            f"You are about to clear all race data including stats and settings. "
            f"If you are sure you wish to proceed, type `{ctx.prefix}yes`."
        )
        choices = (f"{ctx.prefix}yes", f"{ctx.prefix}no")
        check = lambda m: (m.author == ctx.author and m.channel == ctx.channel and m.content in choices)
        try:
            choice = await ctx.bot.wait_for("message", timeout=20.0, check=check)
        except asyncio.TimeoutError:
            return await ctx.send("No response. Race wipe cancelled.")

        if choice.content.lower() == f"{ctx.prefix}yes":
            await self.config.guild(ctx.guild).clear()
            await self.config.clear_all_members(ctx.guild)
            return await ctx.send("Race data has been wiped.")
        else:
            return await ctx.send("Race wipe cancelled.")

    @race.command()
    async def version(self, ctx):
        """Displays the version of race."""
        await ctx.send(f"You are running race version {__version__}.")

    @commands.group()
    @checks.admin_or_permissions(administrator=True)
    async def setrace(self, ctx):
        """Race settings commands."""
        pass

    @setrace.command()
    async def wait(self, ctx, wait: int):
        """Changes the wait time before a race starts.

        This only affects the period where race is still waiting
        for more participants to join the race."""
        if wait < 0:
            return await ctx.send("Really? You're an idiot.")
        await self.config.guild(ctx.guild).Wait.set(wait)
        await ctx.send(f"Waktu menunggu peserta balapan sekarang menjadi {wait} detik.")

    @setrace.group(name="bet")
    async def _bet(self, ctx):
        """Mengatur taruhan untuk balapan."""
        pass

    @_bet.command(name="min")
    async def _min(self, ctx, amount: int):
        """Sets the betting minimum."""
        if amount < 0:
            return await ctx.send("Ayolah!. Pake sedikit otakmu itu.")
        maximum = await self.config.guild(ctx.guild).Bet_Max()
        if amount > maximum:
            return await ctx.send(f"Jumlah maksimum taruhan harus lebih tinggi dari {maximum}.")

        await self.config.guild(ctx.guild).Bet_Min.set(amount)
        await ctx.send(f"Minimum taruhan di set ke {amount}.")

    @_bet.command(name="max")
    async def _max(self, ctx, amount: int):
        """Sets the betting maximum."""
        if amount < 0:
            return await ctx.send("Ayolah!. Pake sedikit otakmu itu.")
        if amount > 2 ** 63 - 1:
            return await ctx.send("Ayolah!. Pake sedikit otakmu itu.")
        minimum = await self.config.guild(ctx.guild).Bet_Min()
        if amount < minimum:
            return await ctx.send(f"Jumlah maksimum harus lebih tinggi dari {minimum}.")

        await self.config.guild(ctx.guild).Bet_Max.set(amount)
        await ctx.send(f"Maksimum taruhan di setting ke {amount}.")

    @_bet.command()
    async def multiplier(self, ctx, multiplier: float):
        """Mengatur multipler taruhan.
        
        If the bot's economy mode is set to global instead of server-based, this setting is not available.
        """
        global_bank = await bank.is_global()
        if global_bank:
            return await ctx.send("This setting is not available for non-server-based bot economies.")
        if multiplier < 0:
            return await ctx.send("So... you want them to lose money... when they win. I'm not doing that.")
        if multiplier == 0:
            return await ctx.send("That means they win nothing. Just turn off betting.")
        if multiplier > 2 ** 63 - 1:
            return await ctx.send("Try a smaller number.")

        await self.config.guild(ctx.guild).Bet_Multiplier.set(multiplier)
        await ctx.send(f"Betting multiplier set to {multiplier}.")

    @_bet.command()
    async def toggle(self, ctx):
        """Hidupkan/Matikan taruhan."""
        current = await self.config.guild(ctx.guild).Bet_Allowed()
        await self.config.guild(ctx.guild).Bet_Allowed.set(not current)
        await ctx.send(f"Taruhan sekarang di {'OFF' if current else 'ON'}.")

    @setrace.command()
    async def mode(self, ctx, mode: str):
        """Changes the race mode.

        Race can either be in normal mode or zoo mode.

        Normal Mode:
            All racers are turtles.

        Zoo Mode:
            Racers are randomly selected from a list of animals with
            different attributes.
        """
        if mode.lower() not in ("zoo", "normal"):
            return await ctx.send("Must select either `zoo` or `normal` as a mode.")

        await self.config.guild(ctx.guild).Mode.set(mode.lower())
        await ctx.send(f"Mode changed to {mode.lower()}")

    @setrace.command()
    async def prize(self, ctx, prize: int):
        """Set hadiah pemenang balapan.

        Mengatur hadiah ke 0 akan membuat player tidak mendapatkan apa-apa.

        Saat pengumpulan hadiah diaktifkan (lihat `[p]setrace togglepool`) hadiahnya 
        akan dibagikan mengikuti:
            1st place 60%
            2nd place 30%
            3rd place 10%

        Example:
            100 results in 60, 30, 10
            130 results in 78, 39, 13

        Apabila pengumpulan hadiah dinonaktifkan, hanya juara 1 yang menang, dan dia akan
        mengambil 100% hadiahnya.
        """
        if prize < 0:
            return await ctx.send("... bukan begitu cara kerja hadiahnya sobat.")
        if prize == 0:
            return await ctx.send("Tidak ada hadiah yang akan diberikan kepada para pemenang.")
        if prize > 2 ** 63 - 1:
            return await ctx.send("Coba angka yang lebih kecil.")
        else:
            currency = await bank.get_currency_name(ctx.guild)
            await self.config.guild(ctx.guild).Prize.set(prize)
            await ctx.send(f"Hadiah diset menjadi {prize} {currency}.")

    @setrace.command(name="togglepool")
    async def _tooglepool(self, ctx):
        """Mematikan/Menghidupkan pengumpulan hadiah.

        Membuat hadiah untuk juara 1st, 2nd, and 3rd.
        Menjadi 60/30/10 dibagi tergantung posisi kemenangan.

        Setidaknya harus ada empat pemain, jika tidak, hanya yang pertama
        yang akan menang!.
        """
        pool = await self.config.guild(ctx.guild).Pooling()
        await self.config.guild(ctx.guild).Pooling.set(not pool)
        await ctx.send(f"Pengumpulan hadiah sekarang {'OFF' if pool else 'ON'}.")

    @setrace.command()
    async def payoutmin(self, ctx, players: int):
        """Sets the number of players needed to payout prizes and bets.

        This sets the required number of players needed to payout prizes.
        If the number of racers aren't met, then nothing is paid out.

        The person starting the race is not counted in this minimum number.
        For example, if you are playing alone vs. the bot and the payout min
        is set to 1, you need 1 human player besides the race starter for a
        payout to occur.

        If you want race to always pay out, then set players to 0.
        """
        if players < 0:
            return await ctx.send("I don't have time for this shit.")
        await self.config.guild(ctx.guild).Payout_Min.set(players)
        if players == 0:
            await ctx.send("Races will now always payout.")
        else:
            plural = "s" if players != 1 else ""
            await ctx.send(f"Races will only payout if there are {players} human player{plural} besides the person that starts the game.")

    async def stats_update(self, ctx):
        names = [player for player, emoji in self.winners[ctx.guild.id]]
        for player in self.players[ctx.guild.id]:
            if player in names:
                position = names.index(player) + 1
                current = await self.config.member(player).Wins.get_raw(str(position))
                await self.config.member(player).Wins.set_raw(str(position), value=current + 1)
            else:
                current = await self.config.member(player).Losses()
                await self.config.member(player).Losses.set(current + 1)

    async def _race_teardown(self, ctx, settings):
        await self.stats_update(ctx)
        await self.distribute_prizes(ctx, settings)
        await self.bet_payouts(ctx, settings)
        self.clear_local(ctx)

    def clear_local(self, ctx):
        self.players[ctx.guild.id].clear()
        self.winners[ctx.guild.id].clear()
        self.bets[ctx.guild.id].clear()
        self.active[ctx.guild.id] = False
        self.started[ctx.guild.id] = False

    async def distribute_prizes(self, ctx, settings):
        if settings["Prize"] == 0 or (settings["Payout_Min"] > len(self.players[ctx.guild.id])):
            return

        if settings["Pooling"] and len(self.players[ctx.guild.id]) > 3:
            first, second, third = self.winners[ctx.guild.id]
            for player, percentage in zip((first[0], second[0], third[0]), (0.6, 0.3, 0.1)):
                if player.bot:
                    continue
                await bank.deposit_credits(player, int(settings["Prize"] * percentage))
        else:
            if self.winners[ctx.guild.id][0][0].bot:
                return
            try:
                await bank.deposit_credits(self.winners[ctx.guild.id][0][0], settings["Prize"])
            except BalanceTooHigh as e:
                await bank.set_balance(self.winners[ctx.guild.id][0][0], e.max_balance)

    async def bet_payouts(self, ctx, settings):
        if not self.bets[ctx.guild.id] or not settings["Bet_Allowed"]:
            return
        multiplier = settings["Bet_Multiplier"]
        first = self.winners[ctx.guild.id][0]
        for user_id, wagers in self.bets[ctx.guild.id].items():
            for jockey, bet in wagers.items():
                if jockey == first[0].id:
                    user = ctx.bot.get_user(user_id)
                    await bank.deposit_credits(user, (int(bet * multiplier)))

    async def bet_conditions(self, ctx, bet, user):
        if not self.active[ctx.guild.id]:
            await ctx.send("Tidak ada balapan sekarang.")
            return False
        elif self.started[ctx.guild.id]:
            await ctx.send("You can't place a bet after the race has started.")
            return False
        elif user not in self.players[ctx.guild.id]:
            await ctx.send("Anda tidak dapat memasang taruhan setelah balapan dimulai.")
            return False
        elif self.bets[ctx.guild.id][ctx.author.id]:
            await ctx.send("Anda sudah memasukkan taruhan untuk balapan.")
            return False

        # Separated the logic such that calls to config only happen if the statements
        # above pass.
        data = await self.config.guild(ctx.guild).all()
        allowed = data["Bet_Allowed"]
        minimum = data["Bet_Min"]
        maximum = data["Bet_Max"]

        if not allowed:
            await ctx.send("Taruhan telah dimatikan.")
            return False
        elif not await bank.can_spend(ctx.author, bet):
            await ctx.send("Anda tidak punya cukup uang untuk memulai taruhan.")
        elif minimum <= bet <= maximum:
            return True
        else:
            await ctx.send(f"Taruhan tidak boleh lebih rendah dari {minimum} atau lebih tinggi dari {maximum}.")
            return False

    async def _build_end_screen(self, ctx, settings, currency, color):
        if len(self.winners[ctx.guild.id]) == 3:
            first, second, third = self.winners[ctx.guild.id]
        else:
            first, second, = self.winners[ctx.guild.id]
            third = None
        payout_msg = self._payout_msg(ctx, settings, currency)
        footer = await self._get_bet_winners(ctx, first[0])
        race_config = (
            f"Prize: {settings['Prize']} {currency}\n"
            f"Prize Pooling: {'ON' if settings['Pooling'] else 'OFF'}\n"
            f"Min. human players for payout: {settings['Payout_Min'] + 1}\n"
            f"Betting Allowed: {'YES' if settings['Bet_Allowed'] else 'NO'}\n"
            f"Bet Multiplier: {settings['Bet_Multiplier']}x"
        )
        embed = discord.Embed(colour=color, title="Race Results")
        embed.add_field(name=f"{first[0].display_name} 🥇", value=first[1].emoji)
        embed.add_field(name=f"{second[0].display_name} 🥈", value=second[1].emoji)
        if third:
            embed.add_field(name=f"{third[0].display_name} 🥉", value=third[1].emoji)
        embed.add_field(name="-" * 90, value="\u200b", inline=False)
        embed.add_field(name="Payouts", value=payout_msg)
        embed.add_field(name="Settings", value=race_config)
        embed.set_footer(text=f"Bet winners: {footer[0:2000]}")
        mentions = "" if first[0].bot else f"{first[0].mention}"
        mentions += "" if second[0].bot else f", {second[0].mention}" if not first[0].bot else f"{second[0].mention}"
        mentions += "" if third is None or third[0].bot else f", {third[0].mention}"
        return mentions, embed

    def _payout_msg(self, ctx, settings, currency):
        if settings["Prize"] == 0:
            return "Tidak ada hadiah uang yang dibagikan."
        elif settings["Payout_Min"] > len(self.players[ctx.guild.id]):
            return "Pembalap tidak cukup untuk memberikan hadiah."
        elif not settings["Pooling"] or len(self.players[ctx.guild.id]) < 4:
            if self.winners[ctx.guild.id][0][0].bot:
                return f"{self.winners[ctx.guild.id][0][0]} adalah pemenangnya!"
            return f"{self.winners[ctx.guild.id][0][0]} mendapatkan {settings['Prize']} {currency}."
        if settings["Pooling"]:
            msg = ""
            first, second, third = self.winners[ctx.guild.id]
            for player, percentage in zip((first[0], second[0], third[0]), (0.6, 0.3, 0.1)):
                if player.bot:
                    continue
                msg += f'{player.display_name} mendapatkan {int(settings["Prize"] * percentage)} {currency}. '
            return msg

    async def _get_bet_winners(self, ctx, winner):
        bet_winners = []
        multiplier = await self.config.guild(ctx.guild).Bet_Multiplier()
        for better, bets in self.bets[ctx.guild.id].items():
            for jockey, bet in bets.items():
                if jockey == winner.id:
                    better_obj = ctx.guild.get_member(better)
                    bet_winners.append(f"{better_obj.display_name}: {bet * multiplier}")
        return ", ".join(bet_winners) if bet_winners else "None."

    async def _game_setup(self, ctx):
        mode = await self.config.guild(ctx.guild).Mode()
        users = self.players[ctx.guild.id]
        if mode == "zoo":
            players = [(Animal(*random.choice(racers)), user) for user in users]
            if len(players) == 1:
                players.append((Animal(*random.choice(racers)), ctx.bot.user))
        else:
            players = [(Animal(":turtle:", "slow"), user) for user in users]
            if len(players) == 1:
                players.append((Animal(":turtle:", "slow"), ctx.bot.user))
        return players

    async def run_game(self, ctx):
        players = await self._game_setup(ctx)
        setup = "\u200b\n" + "\n".join(
            f":carrot: **{animal.current}** 🏁[{jockey.display_name}]" for animal, jockey in players
        )
        track = await ctx.send(setup)
        while not all(animal.position == 0 for animal, jockey in players):

            await asyncio.sleep(2.0)
            fields = []
            for animal, jockey in players:
                if animal.position == 0:
                    fields.append(f":carrot: **{animal.current}** 🏁  [{jockey.display_name}]")
                    continue
                animal.move()
                fields.append(f":carrot: **{animal.current}** 🏁  [{jockey.display_name}]")
                if animal.position == 0 and len(self.winners[ctx.guild.id]) < 3:
                    self.winners[ctx.guild.id].append((jockey, animal))
            t = "\u200b\n" + "\n".join(fields)
            try:
                await track.edit(content=t)
            except discord.errors.NotFound:
            	pass
