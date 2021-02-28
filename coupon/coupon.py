import discord
import uuid

from redbot.core import bank, checks, commands, Config
from redbot.core.errors import BalanceTooHigh
from redbot.core.utils.chat_formatting import box, humanize_number, pagify


async def pred(ctx):
    global_bank = await bank.is_global()
    if not global_bank:
        return True
    else:
        return False


global_bank_check = commands.check(pred)


class Coupon(commands.Cog):
    """Membuat kupon untuk kredit.

    Bank harus berada dalam guild mode, bukan global mode untuk mengaktifkan ini."""

    async def red_delete_data_for_user(self, **kwargs):
        """Tidak ada yang dapat dihapus."""
        return

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 2779691001, force_registration=True)

        default_guild = {"coupons": {}}

        self.config.register_guild(**default_guild)

    @commands.guild_only()
    @commands.group()
    @global_bank_check
    async def coupon(self, ctx):
        """Command Kupon."""
        pass

    @coupon.command(name="clearall")
    @checks.mod_or_permissions(manage_guild=True)
    @global_bank_check
    async def _clearall_coupon(self, ctx):
        """Menghapus semua kupon yang belum di klaim."""
        await self.config.guild(ctx.guild).clear()
        await ctx.send("Semua kode kupon yang belum di klaim telah dihapus dari database.")

    @coupon.command(name="create")
    @checks.admin_or_permissions(manage_guild=True)
    @global_bank_check
    async def _create_coupon(self, ctx, credits: int):
        """Membuat kode unik kupon"""
        if credits > 2 ** 63 - 1:
            return await ctx.send("Coba gunakan nomer yang lebih kecil.")
        if credits < 0:
            return await ctx.send("Nice try.")
        code = str(uuid.uuid4())
        try:
            settings = await self.config.guild(ctx.guild).coupons()
            settings.update({code: credits})
            await self.config.guild(ctx.guild).coupons.set(settings)
            credits_name = await bank.get_currency_name(ctx.guild)
            await ctx.author.send(f"Kupon dibuat untuk `{humanize_number(credits)}` {credits_name}.\nKodenya adalah: `{code}`")
        except discord.Forbidden:
            await ctx.send("Kode tidak dapat dikirimkan melalui DM, karena kemungkinan kamu menolak semua DM.")

    @coupon.command(name="list")
    @checks.admin_or_permissions(manage_guild=True)
    @global_bank_check
    async def _list_coupon(self, ctx):
        """Melihat kode kupon yang aktif."""
        settings = await self.config.guild(ctx.guild).coupons()
        SPACE = "\N{SPACE}"
        msg = f"[Code]{SPACE * 30} | [Credits]\n"
        if len(settings) == 0:
            msg += "Tidak ada kode yang aktif."
        else:
            for code, credits in settings.items():
                msg += f"{code} | {humanize_number(credits)}\n"
        for text in pagify(msg):
            await ctx.send(box(text, lang="ini"))

    @coupon.command(name="redeem")
    @global_bank_check
    async def _redeem_coupon(self, ctx, coupon: str):
        """Klaim kupon."""
        if len(coupon) == 36:
            settings = await self.config.guild(ctx.guild).coupons()
            if coupon in settings:
                credits = settings[coupon]
                credits_name = await bank.get_currency_name(ctx.guild)
                try:
                    await bank.deposit_credits(ctx.author, credits)
                    extra = ""
                except BalanceTooHigh as e:
                    await bank.set_balance(ctx.author, e.max_balance)
                    extra = f"Uang kamu sudah mencapai batas tertinggi ekonomi {humanize_number(e.max_balance)} {credits_name}."
                del settings[coupon]
                await self.config.guild(ctx.guild).coupons.set(settings)
                await ctx.send(f"Saya menambahkan {humanize_number(credits)} {credits_name} ke akun kamu. {extra}")
            else:
                await ctx.send("Kode kupon ini tidak tersedia atau mungkin telah di klaim oleh member lain.")
        else:
            await ctx.send("Kode kupon kamu tidak valid.")
