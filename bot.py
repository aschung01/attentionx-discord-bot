import os
import json
import certifi
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from interactions import (
    Client,
    Intents,
    slash_command,
    slash_option,
    component_callback,
    SlashContext,
    OptionType,
    SlashCommandChoice,
    Button,
    ButtonStyle,
    ActionRow,
    ComponentContext,
)

load_dotenv()

os.environ["SSL_CERT_FILE"] = certifi.where()

SPREADSHEET_ID = "1XRZl3_TEYgBJ5-g60uglEZjU1B_McvWd7yq36Gsod48"

# Global dictionary
message_id_to_row = {}


# Load the dictionary from the JSON file when the bot starts
def load_message_ids():
    global message_id_to_row
    try:
        with open("message_ids.json", "r") as file:
            message_id_to_row = json.load(file)
    except FileNotFoundError:
        pass  # It's okay if the file doesn't exist yet


# Save the dictionary to the JSON file
def save_message_ids():
    with open("message_ids.json", "w") as file:
        json.dump(message_id_to_row, file)


load_message_ids()

# Initialize bot
bot = Client(intents=Intents.DEFAULT)

# Set up Google Sheets client
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
]

creds = ServiceAccountCredentials.from_json(
    json.loads(os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY")), scope
)
spreadsheet_client = gspread.authorize(creds)
sheet = spreadsheet_client.open_by_key(SPREADSHEET_ID).sheet1


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


@slash_command(
    name="start",
    description="GPU 사용 시작!!",
)
@slash_option(
    name="사용팀명",
    argument_name="team_name",
    description="팀명을 선택해주세요.",
    required=True,
    opt_type=OptionType.STRING,
    choices=[
        SlashCommandChoice(
            name="retrieval-augmented-generation",
            value="retrieval-augmented-generation",
        ),
        SlashCommandChoice(name="memory-enhanced-agent", value="memory-enhanced-agent"),
        SlashCommandChoice(name="gpteacher", value="gpteacher"),
        SlashCommandChoice(name="multimodal-generation", value="multimodal-generation"),
        SlashCommandChoice(name="video-llama-drive", value="video-llama-drive"),
        SlashCommandChoice(name="video-captioning", value="video-captioning"),
    ],
)
@slash_option(
    name="사용목적",
    argument_name="usage_purpose",
    description="GPU 사용 목적을 입력해주세요.",
    required=True,
    min_length=10,
    opt_type=OptionType.STRING,
)
async def _submit(ctx: SlashContext, usage_purpose: str, team_name: str):
    if ctx.user.username != "aschung01":
        if ctx.channel is None:
            await ctx.send(content="'서버사용-hardware' 채널에서 이용해주세요.", ephemeral=True)
            return
        if ctx.channel.name != "서버사용-hardware":
            await ctx.send(content="'서버사용-hardware' 채널에서 이용해주세요.", ephemeral=True)
            return

    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Add to Google Sheets
    sheet.append_row([team_name, None, None, usage_purpose])

    # After appending to the sheet
    last_row = len(sheet.col_values(1))  # Assuming column 1 has data for all rows
    sheet.update_cell(last_row, 2, start_time)  # Add start time as datetime

    # Send the confirmation message with a 'check' button
    button = Button(style=ButtonStyle.BLUE, label="사용 종료", custom_id="check_button")
    action_row = ActionRow(button)
    msg = await ctx.send(
        content=f"""## **{team_name} 팀 GPU 이용 시작 🔥**
📍 **이용 시작:**  {start_time}
📍 **사용 목적:**  {usage_purpose}

*GPU 이용이 완료되면, 종료 시각이 기록되도록 꼭 아래 버튼을 클릭해주세요.*
""",
        components=[action_row],
    )
    # Save the message ID and row number
    message_id_to_row[
        str(msg.id)
    ] = last_row  # Convert msg.id to string because JSON keys must be strings

    save_message_ids()


@component_callback("check_button")
async def check_button(ctx: ComponentContext):
    message_id = str(ctx.message_id)
    if message_id not in message_id_to_row:
        await ctx.send(
            content="이미 처리된 요청이거나 확인할 수 없는 요청입니다.",
            ephemeral=True,
        )
        return

    end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet_row = message_id_to_row[message_id]
    sheet.update_cell(sheet_row, 3, end_time)
    team_name, start_time, end_time, usage_purpose = sheet.row_values(sheet_row)

    if ctx.channel:
        # Get the message using its ID
        original_msg = await ctx.channel.fetch_message(message_id)
        # Edit the fetched message
        await original_msg.edit(
            content=f"""## **{team_name} 팀 GPU 이용 기록 🔥**
    📍 **이용 시작:**  {start_time}
    📍 **이용 종료:**  {end_time}
    📍 **사용 목적:**  {usage_purpose}""",
            components=[],
        )

    # Once the time is updated, remove the message ID from the dictionary
    del message_id_to_row[message_id]
    save_message_ids()

    await ctx.send(content="GPU 이용 종료 시각이 기록됐습니다!", ephemeral=True)


if __name__ == "__main__":
    bot.start(os.environ.get("DISCORD_BOT_TOKEN"))
