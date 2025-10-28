#!/usr/bin/env python3
"""
INTERNET SELL APP BOT - RENDER COMPATIBLE
500MB = ₹100, 1GB = ₹200
Withdrawal after 10 referrals only
"""

import os
import sqlite3
import logging
import secrets
import string
import asyncio

# Render compatible imports
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
except ImportError:
    print("Installing required packages...")
    import subprocess
    subprocess.run(["pip", "install", "python-telegram-bot==20.7"])
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Configuration - Environment variables se lego
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8319114937:AAFFIwvLP3FHtJmMJ-C-9ILQ3U-oFfAdOGk')
CHANNEL_LINK = "https://t.me/+kTvYd3_mSbs2MWNl"

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

class RenderInternetBot:
    def __init__(self, token: str):
        self.application = Application.builder().token(token).build()
        self.setup_database()
        self.setup_handlers()
        print("🤖 Bot initialized successfully!")
    
    def setup_database(self):
        """Database setup for Render"""
        try:
            self.conn = sqlite3.connect('/tmp/internet_bot.db', check_same_thread=False)
            cursor = self.conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    joined_channel BOOLEAN DEFAULT FALSE,
                    referral_code TEXT UNIQUE,
                    referred_by TEXT,
                    referral_count INTEGER DEFAULT 0,
                    balance INTEGER DEFAULT 0,
                    app_access BOOLEAN DEFAULT FALSE,
                    withdrawal_access BOOLEAN DEFAULT FALSE,
                    joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    referrer_id INTEGER,
                    referred_id INTEGER,
                    referral_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            self.conn.commit()
            print("✅ Database setup complete!")
            
        except Exception as e:
            print(f"❌ Database error: {e}")
    
    def setup_handlers(self):
        """Setup bot handlers"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("referral", self.referral_command))
        self.application.add_handler(CommandHandler("balance", self.balance_command))
        self.application.add_handler(CommandHandler("app", self.app_command))
        self.application.add_handler(CommandHandler("withdraw", self.withdraw_command))
        self.application.add_handler(CallbackQueryHandler(self.button_handler))
        print("✅ Handlers setup complete!")
    
    def generate_referral_code(self):
        """Generate unique referral code"""
        while True:
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM users WHERE referral_code = ?", (code,))
            if not cursor.fetchone():
                return code
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        try:
            user_id = update.effective_user.id
            username = update.effective_user.username
            first_name = update.effective_user.first_name
            
            # Check referral
            if context.args:
                referral_code = context.args[0]
                await self.handle_referral(user_id, referral_code)
            
            # Register user
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = cursor.fetchone()
            
            if not user:
                referral_code = self.generate_referral_code()
                cursor.execute(
                    "INSERT INTO users (user_id, username, first_name, referral_code) VALUES (?, ?, ?, ?)",
                    (user_id, username, first_name, referral_code)
                )
                self.conn.commit()
                print(f"✅ New user registered: {user_id}")
            
            # Check channel join status
            cursor.execute("SELECT joined_channel FROM users WHERE user_id = ?", (user_id,))
            user_data = cursor.fetchone()
            
            if not user_data or not user_data[0]:
                await self.show_channel_join_message(update, context)
            else:
                await self.show_main_menu(update, context, user_id)
            
        except Exception as e:
            print(f"Start command error: {e}")
            await update.message.reply_text("❌ Error occurred. Please try again.")
    
    async def handle_referral(self, referred_user_id: int, referral_code: str):
        """Handle referral registration"""
        try:
            cursor = self.conn.cursor()
            
            # Find referrer
            cursor.execute("SELECT user_id FROM users WHERE referral_code = ?", (referral_code,))
            referrer = cursor.fetchone()
            
            if referrer and referrer[0] != referred_user_id:
                referrer_id = referrer[0]
                
                # Check if already referred
                cursor.execute(
                    "SELECT * FROM referrals WHERE referrer_id = ? AND referred_id = ?", 
                    (referrer_id, referred_user_id)
                )
                if not cursor.fetchone():
                    # Add referral
                    cursor.execute(
                        "INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)",
                        (referrer_id, referred_user_id)
                    )
                    
                    # Update referral count and balance
                    cursor.execute(
                        "UPDATE users SET referral_count = referral_count + 1, balance = balance + 15 WHERE user_id = ?",
                        (referrer_id,)
                    )
                    
                    # Check if reached 10 referrals for withdrawal access
                    cursor.execute("SELECT referral_count FROM users WHERE user_id = ?", (referrer_id,))
                    ref_count = cursor.fetchone()[0]
                    
                    if ref_count >= 10:
                        cursor.execute(
                            "UPDATE users SET withdrawal_access = TRUE WHERE user_id = ?",
                            (referrer_id,)
                        )
                    
                    # Update referred_by for new user
                    cursor.execute(
                        "UPDATE users SET referred_by = ? WHERE user_id = ?",
                        (referral_code, referred_user_id)
                    )
                    
                    self.conn.commit()
                    
                    # Notify referrer
                    try:
                        cursor.execute("SELECT referral_count, balance FROM users WHERE user_id = ?", (referrer_id,))
                        ref_data = cursor.fetchone()
                        message = f"🎉 New Referral!\n\nYou got ₹15 for new referral!\nTotal Referrals: {ref_data[0]}\nBalance: ₹{ref_data[1]}"
                        
                        if ref_data[0] >= 10:
                            message += "\n\n🎊 Congratulations! You now have withdrawal access!"
                        
                        await self.application.bot.send_message(
                            chat_id=referrer_id,
                            text=message
                        )
                    except:
                        pass
                    
                    print(f"✅ Referral added: {referrer_id} -> {referred_user_id}")
        
        except Exception as e:
            logging.error(f"Referral error: {e}")
    
    async def show_channel_join_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show channel join requirement message"""
        keyboard = [
            [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)],
            [InlineKeyboardButton("✅ Verify Join", callback_data="verify_join")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message_text = """
🤖 **Welcome to Internet Sell App Bot!**

💰 **Earn Money by Selling Internet:**

📊 **Internet Selling Rates:**
• 500MB Internet Sell = ₹100
• 1GB Internet Sell = ₹200

🎁 **How to Get Started:**
1. Join our official channel
2. Refer 10 friends to join
3. Get Internet Sell App download link
4. Start selling internet & earn money!

👥 **Referral Program:**
• ₹15 per successful referral
• Minimum 10 referrals required for app access
• **Withdrawal after 10 referrals only**
• UPI withdrawal available

👇 **Click below to join channel and start earning!**
        """
        
        await update.message.reply_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        try:
            query = update.callback_query
            await query.answer()
            user_id = query.from_user.id
            
            if query.data == "verify_join":
                await self.verify_channel_join(query, context)
            elif query.data == "main_menu":
                await self.show_main_menu_from_query(query, context)
            elif query.data == "get_referral":
                await self.show_referral_info(query, context)
            elif query.data == "check_balance":
                await self.show_balance_from_query(query, context)
            elif query.data == "get_app_link":
                await self.get_app_link(query, context)
            elif query.data == "withdraw_earnings":
                await self.withdraw_earnings(query, context)
                
        except Exception as e:
            print(f"Button handler error: {e}")
    
    async def verify_channel_join(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Verify if user joined channel"""
        user_id = query.from_user.id
        
        try:
            # Update database
            cursor = self.conn.cursor()
            cursor.execute("UPDATE users SET joined_channel = TRUE WHERE user_id = ?", (user_id,))
            self.conn.commit()
            
            success_text = """
✅ **Channel Join Verified Successfully!**

🎉 **Welcome to Internet Sell App Program!**

💰 **Earn Money by Selling Internet:**
• 500MB Internet Sell = ₹100
• 1GB Internet Sell = ₹200

📊 **Next Steps:**
1. Share your referral link with friends
2. Get 10 referrals to unlock the app
3. Earn ₹15 per referral
4. **Withdrawal after 10 referrals only**
5. UPI withdrawal available

🎯 **Minimum 10 referrals required** to get:
• Internet Sell App download link
• Withdrawal access

Use /referral to get your personal referral link!
            """
            
            await query.edit_message_text(
                success_text,
                parse_mode='Markdown'
            )
            
            # Show main menu after verification
            await self.show_main_menu_from_query(query, context)
                
        except Exception as e:
            print(f"Verify error: {e}")
            await query.edit_message_text(
                "✅ **Channel Join Verified!**\n\nUse /referral to get started!",
                parse_mode='Markdown'
            )
    
    async def show_main_menu_from_query(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Show main menu after verification (from callback query)"""
        user_id = query.from_user.id
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT referral_count, balance, app_access, withdrawal_access FROM users WHERE user_id = ?", (user_id,))
        user_data = cursor.fetchone()
        
        referral_count = user_data[0] if user_data else 0
        balance = user_data[1] if user_data else 0
        app_access = user_data[2] if user_data else False
        withdrawal_access = user_data[3] if user_data else False
        
        status_emoji = "✅" if app_access else "❌"
        withdrawal_emoji = "✅" if withdrawal_access else "❌"
        remaining_refs = 10 - referral_count
        
        # Create menu buttons
        keyboard = [
            [InlineKeyboardButton("📤 Get Referral Link", callback_data="get_referral")],
            [InlineKeyboardButton("💰 Check Balance", callback_data="check_balance")],
            [InlineKeyboardButton("🎁 Get App Link", callback_data="get_app_link")],
        ]
        
        # Add withdrawal button only if access available
        if withdrawal_access:
            keyboard.append([InlineKeyboardButton("💸 Withdraw Earnings", callback_data="withdraw_earnings")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message_text = f"""
🏠 **Main Menu - Internet Sell App**

💰 **Earning Plan:**
• 500MB Internet Sell = ₹100
• 1GB Internet Sell = ₹200
• ₹15 per referral

📊 **Your Stats:**
• Referrals: {referral_count}/10
• Balance: ₹{balance}
• App Access: {status_emoji}
• Withdrawal Access: {withdrawal_emoji}

🎯 **Requirements:**
• Minimum 10 referrals for app access
• Minimum 10 referrals for withdrawal
• ₹15 per referral
• UPI withdrawal available

🔔 **Status:** {remaining_refs} referrals needed for full access
        """
        
        await query.edit_message_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Show main menu (from command)"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT referral_count, balance, app_access, withdrawal_access FROM users WHERE user_id = ?", (user_id,))
        user_data = cursor.fetchone()
        
        referral_count = user_data[0] if user_data else 0
        balance = user_data[1] if user_data else 0
        app_access = user_data[2] if user_data else False
        withdrawal_access = user_data[3] if user_data else False
        
        status_emoji = "✅" if app_access else "❌"
        withdrawal_emoji = "✅" if withdrawal_access else "❌"
        remaining_refs = 10 - referral_count
        
        # Create menu buttons
        keyboard = [
            [InlineKeyboardButton("📤 Get Referral Link", callback_data="get_referral")],
            [InlineKeyboardButton("💰 Check Balance", callback_data="check_balance")],
            [InlineKeyboardButton("🎁 Get App Link", callback_data="get_app_link")],
        ]
        
        # Add withdrawal button only if access available
        if withdrawal_access:
            keyboard.append([InlineKeyboardButton("💸 Withdraw Earnings", callback_data="withdraw_earnings")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message_text = f"""
🏠 **Main Menu - Internet Sell App**

💰 **Earning Plan:**
• 500MB Internet Sell = ₹100
• 1GB Internet Sell = ₹200
• ₹15 per referral

📊 **Your Stats:**
• Referrals: {referral_count}/10
• Balance: ₹{balance}
• App Access: {status_emoji}
• Withdrawal Access: {withdrawal_emoji}

🎯 **Requirements:**
• Minimum 10 referrals for app access
• Minimum 10 referrals for withdrawal
• ₹15 per referral
• UPI withdrawal available

🔔 **Status:** {remaining_refs} referrals needed for full access
        """
        
        await update.message.reply_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def show_referral_info(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Show referral information"""
        user_id = query.from_user.id
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT referral_code, referral_count, withdrawal_access FROM users WHERE user_id = ?", (user_id,))
        user_data = cursor.fetchone()
        
        referral_code = user_data[0]
        referral_count = user_data[1]
        withdrawal_access = user_data[2]
        
        bot_username = (await context.bot.get_me()).username
        referral_link = f"https://t.me/{bot_username}?start={referral_code}"
        
        withdrawal_status = "✅ Available" if withdrawal_access else f"❌ Need {10 - referral_count} more referrals"
        
        message_text = f"""
📤 **Your Referral System**

🔗 **Your Referral Link:**
`{referral_link}`

📊 **Your Referrals:** {referral_count}/10
💰 **Earnings:** ₹{referral_count * 15}
💸 **Withdrawal Access:** {withdrawal_status}

🎯 **Requirements:**
• Minimum 10 referrals for app access
• Minimum 10 referrals for withdrawal
• ₹15 per successful referral
• UPI withdrawal available

💡 **How it works:**
1. Share your referral link
2. When friends join using your link, you get ₹15
3. Complete 10 referrals to get:
   • Internet Sell App download
   • Withdrawal access
4. Start selling internet: 500MB=₹100, 1GB=₹200
        """
        
        keyboard = [
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")],
            [InlineKeyboardButton("📢 Share Link", url=f"https://t.me/share/url?url={referral_link}&text=Join%20Internet%20Sell%20App%20-%20Earn%20Money%20by%20selling%20internet!%20500MB%3D%E2%82%B9100%2C%201GB%3D%E2%82%B9200%20%F0%9F%92%B0")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def show_balance_from_query(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Show user balance from callback"""
        user_id = query.from_user.id
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT balance, referral_count, withdrawal_access FROM users WHERE user_id = ?", (user_id,))
        user_data = cursor.fetchone()
        
        balance = user_data[0] if user_data else 0
        referral_count = user_data[1] if user_data else 0
        withdrawal_access = user_data[2] if user_data else False
        
        withdrawal_status = "✅ Available" if withdrawal_access else f"❌ Need {10 - referral_count} more referrals"
        
        message_text = f"""
💰 **Your Earnings Summary**

📊 **Current Balance:** ₹{balance}
👥 **Total Referrals:** {referral_count}
💵 **Referral Earnings:** ₹{referral_count * 15}
🎯 **Remaining for Full Access:** {10 - referral_count} referrals
💸 **Withdrawal Access:** {withdrawal_status}

💰 **Internet Selling Rates:**
• 500MB Internet Sell = ₹100
• 1GB Internet Sell = ₹200

💸 **Withdrawal Info:**
• Minimum withdrawal: ₹50
• **Withdrawal after 10 referrals only**
• UPI withdrawal available
• Processed within 24 hours
        """
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def get_app_link(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Provide app link if requirements met"""
        user_id = query.from_user.id
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT referral_count, app_access FROM users WHERE user_id = ?", (user_id,))
        user_data = cursor.fetchone()
        
        referral_count = user_data[0] if user_data else 0
        app_access = user_data[1] if user_data else False
        
        if referral_count >= 10 or app_access:
            # Update app access
            cursor.execute("UPDATE users SET app_access = TRUE WHERE user_id = ?", (user_id,))
            self.conn.commit()
            
            app_link = "https://example.com/internet-sell-app.apk"  # Replace with actual app link
            
            success_text = f"""
🎉 **Congratulations! App Access Granted!**

📲 **Download Internet Sell App:**
{app_link}

💰 **Start Earning Money:**
• 500MB Internet Sell = ₹100
• 1GB Internet Sell = ₹200

📊 **Your Referrals:** {referral_count}
💵 **Referral Balance:** ₹{referral_count * 15}
💸 **Withdrawal Access:** ✅ Available

🚀 **Install the app and start selling internet today!**
            """
            
            await query.edit_message_text(
                success_text,
                parse_mode='Markdown'
            )
        else:
            remaining = 10 - referral_count
            await query.edit_message_text(
                f"❌ **App Access Not Available Yet!**\n\n"
                f"📊 **Your Progress:** {referral_count}/10 referrals\n"
                f"🎯 **Remaining:** {remaining} referrals needed\n\n"
                f"💡 **Complete {remaining} more referrals to get:**\n"
                f"• Internet Sell App download link\n"
                f"• Withdrawal access\n\n"
                f"💰 **Earning Potential after App Access:**\n"
                f"• 500MB Internet Sell = ₹100\n"
                f"• 1GB Internet Sell = ₹200",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📤 Get Referral Link", callback_data="get_referral")],
                    [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
                ])
            )
    
    async def withdraw_earnings(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Handle withdrawal requests"""
        user_id = query.from_user.id
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT balance, referral_count, withdrawal_access FROM users WHERE user_id = ?", (user_id,))
        user_data = cursor.fetchone()
        
        balance = user_data[0] if user_data else 0
        referral_count = user_data[1] if user_data else 0
        withdrawal_access = user_data[2] if user_data else False
        
        if not withdrawal_access:
            remaining = 10 - referral_count
            await query.edit_message_text(
                f"❌ **Withdrawal Access Not Available!**\n\n"
                f"📊 **Your Referrals:** {referral_count}/10\n"
                f"🎯 **Remaining:** {remaining} referrals needed\n\n"
                f"💡 **Complete {remaining} more referrals to unlock withdrawal access!**\n\n"
                f"💰 **Current Balance:** ₹{balance}\n"
                f"💵 **You'll earn:** ₹{remaining * 15} more from referrals",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📤 Get Referral Link", callback_data="get_referral")],
                    [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
                ])
            )
            return
        
        if balance >= 50:
            message_text = f"""
💸 **Withdrawal Request**

💰 **Available Balance:** ₹{balance}
👥 **Total Referrals:** {referral_count}/10 ✅
💸 **Withdrawal Access:** ✅ Available

📱 **Withdrawal Method:** UPI

📝 **Process:**
1. Minimum withdrawal: ₹50
2. Processed within 24 hours
3. UPI ID required

📨 Please send your UPI ID to process withdrawal.

Send your UPI ID in this format:
`/withdraw your_upi_id@okbank`
            """
            
            await query.edit_message_text(
                message_text,
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(
                f"❌ **Insufficient Balance!**\n\n"
                f"💰 **Current Balance:** ₹{balance}\n"
                f"🎯 **Minimum Required:** ₹50\n\n"
                f"💡 **Complete more referrals to increase your balance!**\n"
                f"• ₹15 per referral\n"
                f"• Withdrawal access: ✅ Available\n"
                f"• Then earn: 500MB=₹100, 1GB=₹200",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📤 Get Referral Link", callback_data="get_referral")],
                    [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
                ])
            )
    
    # Command handlers
    async def referral_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /referral command"""
        await self.show_referral_info(update, context)
    
    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /balance command"""
        await self.show_balance_from_query(update, context)
    
    async def app_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /app command"""
        await self.get_app_link(update, context)
    
    async def withdraw_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /withdraw command"""
        user_id = update.effective_user.id
        
        if context.args and len(context.args) > 0:
            upi_id = context.args[0]
            await self.process_withdrawal(update, context, user_id, upi_id)
        else:
            await self.withdraw_earnings(update, context)
    
    async def process_withdrawal(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, upi_id: str):
        """Process withdrawal request"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT balance, withdrawal_access FROM users WHERE user_id = ?", (user_id,))
        user_data = cursor.fetchone()
        
        balance = user_data[0] if user_data else 0
        withdrawal_access = user_data[1] if user_data else False
        
        if not withdrawal_access:
            await update.message.reply_text(
                "❌ **Withdrawal access not available!**\n"
                "Complete 10 referrals to unlock withdrawal."
            )
            return
        
        if balance >= 50:
            # Process withdrawal
            cursor.execute("UPDATE users SET balance = 0 WHERE user_id = ?", (user_id,))
            self.conn.commit()
            
            await update.message.reply_text(
                f"✅ **Withdrawal Request Submitted!**\n\n"
                f"💰 **Amount:** ₹{balance}\n"
                f"📱 **UPI ID:** {upi_id}\n"
                f"⏰ **Processing:** Within 24 hours\n\n"
                f"📞 Contact support for any queries."
            )
        else:
            await update.message.reply_text(
                "❌ **Insufficient balance for withdrawal!**\n"
                "Minimum withdrawal amount is ₹50."
            )

# Main execution
if __name__ == '__main__':
    print("🚀 Starting Internet Sell Bot on Render...")
    print(f"📝 Bot Token: {BOT_TOKEN[:10]}...")
    
    try:
        bot = RenderInternetBot(BOT_TOKEN)
        print("✅ Bot setup complete. Starting polling...")
        bot.application.run_polling()
    except Exception as e:
        print(f"❌ Failed to start bot: {e}")
