import asyncio
import discord

from discord.utils import get
from datetime import datetime, timedelta

from redbot.core import Config, checks, commands
from redbot.core.utils.predicates import MessagePredicate
from redbot.core.utils.antispam import AntiSpam

from redbot.core.bot import Red


class Application(commands.Cog):
    """
    Simple application cog, basically.
    **Use `[p]applysetup` first.**
    """

    __author__ = "saurichable"
    __version__ = "1.2.6"

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self, 5641654654621651651, force_registration=True
        )
        self.antispam = {}
        self.config.register_guild(
            is_set=False,
            applicant_id=None,
            accepter_id=None,
            channel_id=None,
            applicant_role=True,
            questions=[
                ["Apa posisi yang kamu inginkan?", "Position", 120],
                ["Siapa nama asli kamu?", "Name", 120],
                ["Berapa umurmu?", "Age", 120],
                ["Kamu tinggal di daerah apa?", "Daerah", 120],
                ["Berapa hari dalam seminggu kamu aktif discord?", "Active days/week", 120],
                ["Berapa jam sehari kamu aktif discord?", "Active hours/day", 120],
                ["Apa kamu punya pengalaman sebelumnya menjadi staff di server lain? Kalau ada, tolong jabarkan.", "Previous experience", 120],
                ["Mengapa kamu mau menjadi staff diserver kami?", "Reason", 120],
                ],
        )

    @commands.command()
    @commands.guild_only()
    @checks.bot_has_permissions(manage_roles=True)
    async def apply(self, ctx: commands.Context):
        """Apply to be a staff member."""
        if not await self.config.guild(ctx.guild).is_set():
            return await ctx.send("Uh oh, konfigurasi tidak benar. Tanya admin untuk memproses ini.")

        if await self.config.guild(ctx.guild).applicant_role():
            try:
                role_add = get(ctx.guild.roles, id = await self.config.guild(ctx.guild).applicant_id())
            except TypeError:
                role_add = None
            if not role_add:
                role_add = get(ctx.guild.roles, name = "Calon Moderator")
                if not role_add:
                    return await ctx.send("Uh oh, konfigurasi tidak benar. Tanya admin untuk memproses ini.")
        try:
            channel = get(ctx.guild.text_channels, id = await self.config.guild(ctx.guild).channel_id())
        except TypeError:
            channel = None
        if not channel:
            channel = get(ctx.guild.text_channels, name = "applications")
            if not channel:
                return await ctx.send("Uh oh, konfigurasi tidak benar. Tanya admin untuk memproses ini.")
        if ctx.guild not in self.antispam:
            self.antispam[ctx.guild] = {}
        if ctx.author not in self.antispam[ctx.guild]:
            self.antispam[ctx.guild][ctx.author] = AntiSpam([(timedelta(days=2), 1)])
        if self.antispam[ctx.guild][ctx.author].spammy:
            return await ctx.send("Uh oh, kamu melakukan pendaftaran terlalu cepat!")
        if not role_add:
            return await ctx.send(
                "Uh oh. Admin belum menambahkan role yang dibutuhkan, coba tanya admin."
            )
        if not channel:
            return await ctx.send(
                "Uh oh. Admin belum menambahkan role yang dibutuhkan, coba tanya admin."
            )
        try:
            await ctx.author.send(
                "Ayo kita mulai sekarang!"
            )
        except discord.Forbidden:
            return await ctx.send(
                "Hmm aku tidak bisa mengirim DM kepadamu, apa kamu menutup DM kamu?"
            )
        await ctx.send(f"Okay, {ctx.author.mention}, aku telah mengirimkan kamu DM.")

        embed = discord.Embed(color=await ctx.embed_colour(), timestamp=datetime.now())
        embed.set_author(name="Aplikasi baru!", icon_url=ctx.author.avatar_url)
        embed.set_footer(
            text=f"{ctx.author.name}#{ctx.author.discriminator} ({ctx.author.id})"
        )
        embed.title = (
            f"User: {ctx.author.name}#{ctx.author.discriminator} ({ctx.author.id})"
        )

        def check(m):
            return m.author == ctx.author and m.channel == ctx.author.dm_channel

        questions = await self.config.guild(ctx.guild).questions() # list of lists
        default_questions = await self._default_questions_list() # default list of lists just in case
        for i, question in enumerate(questions): # for list in lists
            try:
                await ctx.author.send(question[0])
                timeout = question[2]
                shortcut = question[1]
            except TypeError:
                await ctx.author.send(default_questions[i][0])
                timeout = default_questions[i][2]
                shortcut = default_questions[i][1]
            try:
                answer = await self.bot.wait_for("message", timeout=timeout, check=check)
            except asyncio.TimeoutError:
                return await ctx.author.send("Ah kamu terlalu lama, coba lagi deh nanti ya!")
            embed.add_field(name=shortcut + ":", value=answer.content)

        await channel.send(embed=embed)

        await ctx.author.add_roles(role_add)
        await ctx.author.send(
            "Aplikasi pendafaran kamu telah diterima dan telah dikirimkan kepada admin. Tunggu pemberitahuan selanjutnya di dalam server ya!"
        )
        self.antispam[ctx.guild][ctx.author].stamp()

    @checks.admin_or_permissions(administrator=True)
    @commands.group(autohelp=True)
    @commands.guild_only()
    @checks.bot_has_permissions(manage_channels=True, manage_roles=True)
    async def setapply(self, ctx: commands.Context):
        """Setting pendaftaran"""
        pass

    @setapply.command(name="setup")
    async def setapply_setup(self, ctx: commands.Context):
        """Go through the initial setup process."""
        pred = MessagePredicate.yes_or_no(ctx)
        role = MessagePredicate.valid_role(ctx)

        applicant = get(ctx.guild.roles, name="Calon Moderator")
        channel = get(ctx.guild.text_channels, name="applications")

        await ctx.send(
            "Ini akan membutuhkan channel dan role khusus, apakah perlu saya buatkan? (yes/no)"
        )
        try:
            await self.bot.wait_for("message", timeout=30, check=pred)
        except asyncio.TimeoutError:
            return await ctx.send("You took too long. Try again, please.")
        if not pred.result:
            return await ctx.send("Setup cancelled.")
        if not applicant:
            await ctx.send(
                "Apa kamu ingin pendaftar mendapatkan role khusus? (yes/no)"
            )
            try:
                await self.bot.wait_for("message", timeout=30, check=pred)
            except asyncio.TimeoutError:
                return await ctx.send("You took too long. Try again, please.")
            if pred.result:
                await self.config.guild(ctx.guild).applicant_role.set(True)
                try:
                    applicant = await ctx.guild.create_role(
                        name="Calon Moderator", reason="Application cog setup"
                    )
                except discord.Forbidden:
                    return await ctx.send(
                        "Uh oh. Terlihat saya tidak punya hak untuk memberikan role."
                    )
                await self.config.guild(ctx.guild).applicant_id.set(applicant.id)
            else:
                await self.config.guild(ctx.guild).applicant_role.set(False)
                await self.config.guild(ctx.guild).applicant_id.set(None)
        if not channel:
            await ctx.send(
                "Apa kamu ingin semua orang dapat melihat hasil pendaftaran para staff? (yes/no)"
            )
            try:
                await self.bot.wait_for("message", timeout=30, check=pred)
            except asyncio.TimeoutError:
                return await ctx.send("You took too long. Try again, please.")
            if pred.result:
                overwrites = {
                    ctx.guild.default_role: discord.PermissionOverwrite(
                        send_messages=False
                    ),
                    ctx.guild.me: discord.PermissionOverwrite(send_messages=True),
                }
            else:
                overwrites = {
                    ctx.guild.default_role: discord.PermissionOverwrite(
                        read_messages=False
                    ),
                    ctx.guild.me: discord.PermissionOverwrite(read_messages=True),
                }
            try:
                channel = await ctx.guild.create_text_channel(
                    "applications",
                    overwrites=overwrites,
                    reason="Application cog setup",
                )
            except discord.Forbidden:
                return await ctx.send(
                    "Uh oh. terlihat saya tidak punya hak untuk mengatur channel ya."
                )
        await ctx.send(f"Role apa yang dapat menerima dan menolak pendaftaran staff?")
        try:
            await self.bot.wait_for("message", timeout=30, check=role)
        except asyncio.TimeoutError:
            return await ctx.send("You took too long. Try again, please.")
        accepter = role.result
        await self.config.guild(ctx.guild).channel_id.set(channel.id)
        await self.config.guild(ctx.guild).accepter_id.set(accepter.id)
        await self.config.guild(ctx.guild).is_set.set(True)
        await ctx.send(
            "You have finished the setup! Please, move your new channel to the category you want it in."
        )

    @setapply.command(name="questions")
    async def setapply_questions(self, ctx: commands.Context):
        """Set custom application questions."""
        current_questions = "**Current questions:**"
        for question in await self.config.guild(ctx.guild).questions():
            try:
                current_questions += "\n" + question[0]
            except TypeError:
                current_questions = "Uh oh, couldn't fetch your questions.\n" + await self._default_questions_string()
                break
        await ctx.send(current_questions)

        same_context = MessagePredicate.same_context(ctx)
        valid_int = MessagePredicate.valid_int(ctx)
        
        await ctx.send("How many questions?")
        try:
            number_of_questions = await self.bot.wait_for("message", timeout=60, check=valid_int)
        except asyncio.TimeoutError:
            return await ctx.send("You took too long. Try again, please.")

        list_of_questions = list()
        for x in range(int(number_of_questions.content)):
            question_list = list()

            await ctx.send("Enter question: ")
            try:
                custom_question = await self.bot.wait_for("message", timeout=60, check=same_context)
            except asyncio.TimeoutError:
                return await ctx.send("You took too long. Try again, please.")
            question_list.append(custom_question.content)

            await ctx.send("Enter how the question will look in final embed (f.e. Name): ")
            try:
                shortcut = await self.bot.wait_for("message", timeout=60, check=same_context)
            except asyncio.TimeoutError:
                return await ctx.send("You took too long. Try again, please.")
            question_list.append(shortcut.content)

            await ctx.send("Enter how many seconds the applicant has to answer: ")
            try:
                time = await self.bot.wait_for("message", timeout=60, check=valid_int)
            except asyncio.TimeoutError:
                return await ctx.send("You took too long. Try again, please.")
            question_list.append(int(valid_int.result))

            list_of_questions.append(question_list)

        await self.config.guild(ctx.guild).questions.set(list_of_questions)
        await ctx.send("Done!")

    @commands.command()
    @commands.guild_only()
    @checks.bot_has_permissions(manage_roles=True)
    async def accept(self, ctx: commands.Context, target: discord.Member):
        """Menerima pendaftaran staff.

        <target> can be a mention or an ID."""
        if not await self.config.guild(ctx.guild).is_set():
            return await ctx.send("Uh oh, the configuration is not correct. Ask the Admins to set it.")

        try:
            accepter = get(ctx.guild.roles, id = await self.config.guild(ctx.guild).accepter_id())
        except TypeError:
            accepter = None
        if not accepter:
            if not ctx.author.guild_permissions.administrator:
                return await ctx.send("Uh oh, you cannot use this command.")
        else:
            if accepter not in ctx.author.roles:
                return await ctx.send("Uh oh, you cannot use this command.")

        role = MessagePredicate.valid_role(ctx)
        if await self.config.guild(ctx.guild).applicant_role():
            try:
                applicant = get(ctx.guild.roles, id = await self.config.guild(ctx.guild).applicant_id())
            except TypeError:
                applicant = None
            if not applicant:
                applicant = get(ctx.guild.roles, name="Calon Moderator")
                if not applicant:
                    return await ctx.send("Uh oh, the configuration is not correct. Ask the Admins to set it.")
            if applicant not in target.roles:
                await target.remove_roles(applicant)
            else:
                return await ctx.send(
                    f"Uh oh. Looks like {target.mention} hasn't applied for anything."
                )
        await ctx.send(f"What role do you want to accept {target.name} as?")
        try:
            await self.bot.wait_for("message", timeout=30, check=role)
        except asyncio.TimeoutError:
            return await ctx.send("You took too long. Try again, please.")
        role_add = role.result
        try:
            await target.add_roles(role_add)
        except discord.Forbidden:
            return await ctx.send("Uh oh, I cannot give them the role. It might be above all of my roles.")
        await ctx.send(f"Accepted {target.mention} as {role_add}.")
        await target.send(f"You have been accepted as {role_add} in {ctx.guild.name}.")

    @commands.command()
    @commands.guild_only()
    @checks.bot_has_permissions(manage_roles=True)
    async def deny(self, ctx: commands.Context, target: discord.Member):
        """Menolak pendaftaran staff.

        <target> can be a mention or an ID"""
        if not await self.config.guild(ctx.guild).is_set():
            return await ctx.send("Uh oh, the configuration is not correct. Ask the Admins to set it.")

        try:
            accepter = get(ctx.guild.roles, id = await self.config.guild(ctx.guild).accepter_id())
        except TypeError:
            accepter = None
        if not accepter:
            if not ctx.author.guild_permissions.administrator:
                return await ctx.send("Uh oh, you cannot use this command.")
        else:
            if accepter not in ctx.author.roles:
                return await ctx.send("Uh oh, you cannot use this command.")

        if await self.config.guild(ctx.guild).applicant_role():
            try:
                applicant = get(ctx.guild.roles, id = await self.config.guild(ctx.guild).applicant_id())
            except TypeError:
                applicant = None
            if not applicant:
                applicant = get(ctx.guild.roles, name="Calon Moderator")
                if not applicant:
                    return await ctx.send("Uh oh, the configuration is not correct. Ask the Admins to set it.")
            if applicant in target.roles:
                await target.remove_roles(applicant)
            else:
                return await ctx.send(
                    f"Uh oh. Looks like {target.mention} hasn't applied for anything."
                )

        await ctx.send("Would you like to specify a reason? (yes/no)")
        pred = MessagePredicate.yes_or_no(ctx)
        try:
            await self.bot.wait_for("message", timeout=30, check=pred)
        except asyncio.TimeoutError:
            return await ctx.send("You took too long. Try again, please.")
        if pred.result:
            await ctx.send("Please, specify your reason now.")

            def check(m):
                return m.author == ctx.author

            try:
                reason = await self.bot.wait_for(
                    "message", timeout=120, check=check
                )
            except asyncio.TimeoutError:
                return await ctx.send("You took too long. Try again, please.")
            await target.send(
                f"Pendaftaran kamu di {ctx.guild.name} telah ditolak.\n*Alasan:* {reason.content}"
            )
        else:
            await target.send(
                f"Pendaftaran kamu di {ctx.guild.name} telah ditolak."
            )
        await ctx.send(f"Denied {target.mention}'s application.")

    async def _default_questions_list(self):
        return [
                ["Apa posisi yang kamu inginkan?", "Posisi", 120],
                ["Siapa nama asli kamu?", "Nama", 120],
                ["Berapa umurmu?", "Umur", 120],
                ["Kamu tinggal di daerah apa?", "Daerah", 120],
                ["Berapa hari dalam seminggu kamu aktif discord?", "Hari aktif/hari", 120],
                ["Berapa jam sehari kamu aktif discord?", "Jam aktif/hari", 120],
                ["Apa kamu punya pengalaman sebelumnya menjadi staff di server lain? Kalau ada, tolong jabarkan.", "Pengalaman sebelumnya", 120],
                ["Mengapa kamu mau menjadi staff diserver kami?", "Alasan", 120],
                ]

    async def _default_questions_string(self):
        list_of_questions = await self._default_questions_list()
        string = "**Pertanyaan default:**"
        for question in list_of_questions:
            string += "\n" + question[0]
        return string