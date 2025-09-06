#!/usr/bin/env python3
"""Interactive chat CLI for testing the healthcare AI service."""

import sys

import httpx
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt


class ChatCLI:
    """Interactive chat interface for the healthcare AI service."""

    def __init__(self, base_url: str = "http://localhost:9001"):
        """Initialize chat CLI."""
        self.base_url = base_url
        self.session_id: str | None = None
        self.console = Console()
        self.client = httpx.Client(timeout=60.0)

    def start(self) -> None:
        """Start the interactive chat session."""
        self.console.print(
            Panel.fit(
                "[bold blue]🏥 Luma Healthcare AI - Interactive Chat[/bold blue]\n"
                "Type your messages to chat with the AI assistant.\n"
                "Commands: /help, /clear, /quit",
                border_style="blue",
            )
        )

        # Test connection
        if not self._test_connection():
            self.console.print("[red]❌ Cannot connect to the service. Make sure it's running on port 9001.[/red]")
            return

        self.console.print("[green]✅ Connected to healthcare AI service[/green]\n")

        # Show test patients
        self._show_test_patients()

        # Main chat loop
        try:
            while True:
                user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]")

                if user_input.lower() in ["/quit", "/exit", "quit", "exit"]:
                    break
                elif user_input.lower() == "/help":
                    self._show_help()
                    continue
                elif user_input.lower() == "/clear":
                    self.session_id = None
                    self.console.print("[yellow]🔄 Session cleared[/yellow]")
                    continue
                elif user_input.strip() == "":
                    continue

                # Send message to AI
                response = self._send_message(user_input)
                if response:
                    self._display_response(response)

        except KeyboardInterrupt:
            pass
        finally:
            self.console.print("\n[yellow]👋 Goodbye![/yellow]")
            self.client.close()

    def _test_connection(self) -> bool:
        """Test connection to the service."""
        try:
            response = self.client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception:
            return False

    def _send_message(self, message: str) -> dict | None:
        """Send message to the AI service."""
        try:
            payload = {"message": message}
            if self.session_id:
                payload["session_id"] = self.session_id

            self.console.print("[dim]💭 Thinking...[/dim]", end="")

            response = self.client.post(
                f"{self.base_url}/conversation", json=payload, headers={"Content-Type": "application/json"}
            )

            # Clear the "thinking" message
            self.console.print("\r" + " " * 20 + "\r", end="\n")

            if response.status_code == 200:
                data = response.json()
                self.session_id = data.get("session_id")
                return data
            else:
                self.console.print(f"[red]❌ API Error: {response.status_code} - {response.text}[/red]")
                return None

        except Exception as e:
            self.console.print(f"[red]❌ Connection error: {e}[/red]")
            return None

    def _display_response(self, response: dict) -> None:
        """Display AI response with nice formatting."""
        assistant_text = response.get("response", "No response")

        self.console.print(
            Panel(
                Markdown(assistant_text),
                title="[bold green]🤖 Healthcare Assistant[/bold green]",
                border_style="green",
                padding=(1, 2),
            )
        )

    def _show_test_patients(self) -> None:
        """Show available test patients."""
        test_patients = [
            "John Smith, 555-123-4567, 1980-01-01",
            "Jane Doe, 555-987-6543, 1985-05-15",
            "Mike Johnson, 555-555-1234, 1975-12-25",
            "Sarah Wilson, 555-444-3333, 1990-08-30",
        ]

        patient_list = "\n".join([f"• {patient}" for patient in test_patients])

        self.console.print(
            Panel(
                f"[bold]Test Patients (Name, Phone, DOB):[/bold]\n\n{patient_list}\n\n"
                "[dim]Use these for testing patient verification[/dim]",
                title="[yellow]📋 Available Test Data[/yellow]",
                border_style="yellow",
            )
        )

    def _show_help(self) -> None:
        """Show help information."""
        help_text = """
[bold]Available Commands:[/bold]
• /help - Show this help message
• /clear - Clear session and start over
• /quit or /exit - Exit the chat

[bold]Example Conversation:[/bold]
1. "Hello, I need help with my appointments"
2. "My name is John Smith, phone 555-123-4567, born 1980-01-01"
3. "Show me my appointments"
4. "Confirm APT_001"

[bold]Tips:[/bold]
• Use exact format for verification: Name, phone (xxx-xxx-xxxx), date (YYYY-MM-DD)
• Appointment IDs are in format APT_XXX (e.g., APT_001)
• The AI will guide you through the verification process
        """

        self.console.print(Panel(help_text.strip(), title="[cyan]❓ Help[/cyan]", border_style="cyan"))


def main():
    """Main entry point for the chat CLI."""
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:9001"

    chat = ChatCLI(base_url)
    chat.start()


if __name__ == "__main__":
    main()
