import os
import sys
import time
import requests
import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.live import Live
from rich.text import Text
import pyfiglet

MAIL_ENDPOINT = "https://api.internal.temp-mail.io/api/v3/email/new"
INBOX_ENDPOINT = "https://api.internal.temp-mail.io/api/v3/email/{email}/messages"
ATTACHMENT_ENDPOINT = "https://api.internal.temp-mail.io/api/v3/attachment/{id}?download=1"

DATA_DIR = Path(".temp_mail_data")
OLD_MAILS_FILE = DATA_DIR / "old_mails.json"
SEEN_MAILS_FILE = DATA_DIR / "seen_mails.json"

console = Console()


def show_logo():
    """Displays the application logo."""
    console.clear()
    banner = pyfiglet.figlet_format("Temp Mail", font="slant")
    console.print(f"[bold green]{banner}[/bold green]")
    logo = Panel(
        "[dim]Your disposable email solution[/dim]",
        title="[bold cyan]Welcome[/bold cyan]",
        border_style="green",
        expand=False,
    )
    console.print(logo)


def get_random_email():
    """Generates a new random email address."""
    try:
        json_data = {"min_name_length": 10, "max_name_length": 10}
        response = requests.post(MAIL_ENDPOINT, json=json_data)
        response.raise_for_status()
        return response.json()["email"]
    except requests.RequestException as e:
        console.print(f"[bold red]Error generating email: {e}[/bold red]")
        return None


def save_email(email):
    """Saves a generated email to the history."""
    DATA_DIR.mkdir(exist_ok=True)
    if not OLD_MAILS_FILE.exists():
        with open(OLD_MAILS_FILE, "w") as f:
            json.dump([], f)

    with open(OLD_MAILS_FILE, "r+") as f:
        try:
            emails = json.load(f)
        except json.JSONDecodeError:
            emails = []
        if email not in emails:
            emails.append(email)
            f.seek(0)
            json.dump(emails, f, indent=4)


def get_old_emails():
    """Retrieves the list of previously generated emails."""
    if not OLD_MAILS_FILE.exists():
        return []
    with open(OLD_MAILS_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def display_emails(emails):
    """Displays a list of emails in a table."""
    if not emails:
        console.print("[yellow]No old emails found.[/yellow]")
        return

    table = Table(title="[bold green]Your Created Emails[/bold green]")
    table.add_column("Index", style="cyan")
    table.add_column("Email Address", style="magenta")

    for i, email in enumerate(emails, 1):
        table.add_row(str(i), email)

    console.print(table)


def login_to_old_email():
    """Allows the user to select an old email to log in to."""
    old_emails = get_old_emails()
    if not old_emails:
        console.print("[yellow]No old emails to log in to.[/yellow]")
        return None

    display_emails(old_emails)
    choice = Prompt.ask(
        "[bold]Enter the index of the email to restore[/bold]",
        choices=[str(i) for i in range(1, len(old_emails) + 1)],
        show_choices=False,
    )
    return old_emails[int(choice) - 1]


def display_inbox(email):
    """Displays the inbox for a given email address with live updates."""
    console.print(Panel(f"Inbox for: [bold green]{email}[/bold green]", expand=False))
    console.print("[dim]Press Ctrl+C to go back to the main menu...[/dim]")

    seen_mail_ids = set()
    if SEEN_MAILS_FILE.exists():
        with open(SEEN_MAILS_FILE, 'r') as f:
            try:
                seen_mail_ids = set(json.load(f))
            except json.JSONDecodeError:
                pass

    with Live(console=console, screen=False, auto_refresh=False) as live:
        while True:
            try:
                table = Table(title="[bold blue]Inbox[/bold blue]")
                table.add_column("From", style="cyan")
                table.add_column("To", style="cyan")
                table.add_column("Subject", style="magenta")
                table.add_column("Body", style="white")
                table.add_column("Attachments", style="yellow")

                url = INBOX_ENDPOINT.format(email=email)
                response = requests.get(url)
                response.raise_for_status()
                messages = response.json()

                new_messages = False
                for msg in messages:
                    msg_id = str(msg["id"])
                    if msg_id not in seen_mail_ids:
                        new_messages = True
                        seen_mail_ids.add(msg_id)

                        attachments = []
                        if msg.get("attachments"):
                            for att in msg["attachments"]:
                                download_url = ATTACHMENT_ENDPOINT.format(id=att['id'])
                                attachments.append(f"[link={download_url}]{att['name']}[/link]")

                        table.add_row(
                            msg["from"],
                            msg["to"],
                            msg["subject"],
                            msg["body_text"][:100] + "..." if len(msg["body_text"]) > 100 else msg["body_text"],
                            "\n".join(attachments) if attachments else "None",
                        )

                if new_messages:
                    live.update(table, refresh=True)
                    with open(SEEN_MAILS_FILE, 'w') as f:
                        json.dump(list(seen_mail_ids), f)


                time.sleep(5)
            except requests.RequestException as e:
                console.print(f"[bold red]Error fetching inbox: {e}[/bold red]")
                time.sleep(5)
            except KeyboardInterrupt:
                break
            except json.JSONDecodeError:
                # No messages yet, just wait
                time.sleep(5)


def remove_all_data():
    """Removes all stored data."""
    console.print("[bold yellow]Removing all old mail data...[/bold yellow]")
    if OLD_MAILS_FILE.exists():
        OLD_MAILS_FILE.unlink()
    if SEEN_MAILS_FILE.exists():
        SEEN_MAILS_FILE.unlink()
    if DATA_DIR.exists():
        try:
            DATA_DIR.rmdir()
        except OSError:
            # Directory might not be empty if other files are there
            pass
    console.print("[bold green]Successfully removed all old mails data.[/bold green]")


def main_menu():
    """Displays the main menu and handles user choices."""
    while True:
        show_logo()
        console.print(Panel(
            "[1] Generate Random Mail\n"
            "[2] See Mails You Created\n"
            "[3] Log In To Old Mails\n"
            "[4] Remove All Old Mail's Data\n"
            "[5] Exit",
            title="[bold cyan]Choose Your Option[/bold cyan]",
            border_style="blue"
        ))

        choice = Prompt.ask(
            "[bold]Choose an option[/bold]", choices=["1", "2", "3", "4", "5"], default="1"
        )

        if choice == "1":
            email = get_random_email()
            if email:
                save_email(email)
                console.print(f"[bold green]Your new email is: {email}[/bold green]")
                display_inbox(email)
        elif choice == "2":
            emails = get_old_emails()
            display_emails(emails)
            Prompt.ask("[bold]Press Enter to go back...[/bold]")
        elif choice == "3":
            email = login_to_old_email()
            if email:
                display_inbox(email)
        elif choice == "4":
            remove_all_data()
            Prompt.ask("[bold]Press Enter to go back...[/bold]")
        elif choice == "5":
            console.print("[bold cyan]Thanks for using Temp Mail! Goodbye![/bold cyan]")
            sys.exit()


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        console.print("\n[bold cyan]Goodbye![/bold cyan]")
        sys.exit(0)