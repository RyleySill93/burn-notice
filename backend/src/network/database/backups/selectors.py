"""Interactive selectors for database backup operations."""

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from loguru import logger

try:
    from blessed import Terminal

    term = Terminal()
    BLESSED_AVAILABLE = True
except ImportError:
    # Fallback if blessed is not installed
    class FallbackTerminal:
        def bold(self, text):
            return text

        def green(self, text):
            return text

        def yellow(self, text):
            return text

        def blue(self, text):
            return text

        def red(self, text):
            return text

        def cyan(self, text):
            return text

        def bright_white(self, text):
            return text

        def reverse(self, text):
            return text

    term = FallbackTerminal()
    BLESSED_AVAILABLE = False

from .s3_restore import S3BackupInfo


def format_backup_size(size_mb: float) -> str:
    """Format backup size in human readable format."""
    if size_mb < 1024:
        return f'{size_mb:.1f} MB'
    else:
        return f'{size_mb/1024:.1f} GB'


def format_backup_age(timestamp: datetime) -> str:
    """Format how old a backup is in human readable format."""
    # Ensure we're comparing timezone-aware datetimes
    now = datetime.now()
    if timestamp.tzinfo is not None:
        # timestamp is timezone-aware, make now aware too
        import pytz

        now = pytz.UTC.localize(datetime.utcnow())
    elif now.tzinfo is not None:
        # now is timezone-aware but timestamp isn't
        timestamp = pytz.UTC.localize(timestamp)

    age = now - timestamp

    if age.days > 365:
        years = age.days // 365
        return f"{years} year{'s' if years > 1 else ''} ago"
    elif age.days > 30:
        months = age.days // 30
        return f"{months} month{'s' if months > 1 else ''} ago"
    elif age.days > 0:
        return f"{age.days} day{'s' if age.days > 1 else ''} ago"
    elif age.seconds > 3600:
        hours = age.seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif age.seconds > 60:
        minutes = age.seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    else:
        return 'just now'


def select_local_backup(backups: List[Path]) -> Optional[Path]:
    """Interactive selector for local backups with arrow key navigation."""
    if not backups:
        logger.error('No backups available to select from')
        return None

    if not BLESSED_AVAILABLE:
        # Fallback to simple selection if blessed is not available
        return _simple_select_local_backup(backups)

    selected_idx = 0  # Default to latest (first) backup

    with term.fullscreen():
        with term.cbreak():
            while True:
                print(term.clear())
                print(term.bold(term.green('✨ Available Local Backups\n')))
                print(term.cyan('Use ↑/↓ arrows to navigate, Enter to select, q to quit'))
                print(term.cyan('─' * 80))

                for i, backup_file in enumerate(backups):
                    size_mb = backup_file.stat().st_size / (1024 * 1024)
                    mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
                    age = format_backup_age(mtime)

                    line = f'  {backup_file.name:<50} {format_backup_size(size_mb):>10}  ({age})'

                    if i == selected_idx:
                        # Highlight selected item
                        if i == 0:
                            print(term.reverse(term.bright_white(f'→ {line} ⭐')))
                        else:
                            print(term.reverse(f'→ {line}'))
                    else:
                        # Normal display
                        if i == 0:
                            print(term.bright_white(f'  {line} ⭐'))
                        else:
                            print(f'  {line}')

                print(term.cyan('─' * 80))
                print(
                    f"\n{term.yellow('[↑/↓]')} Navigate  {term.green('[Enter]')} Select  {term.red('[q/Esc]')} Cancel"
                )

                # Get key input
                key = term.inkey()

                if key.name == 'KEY_UP':
                    selected_idx = max(0, selected_idx - 1)
                elif key.name == 'KEY_DOWN':
                    selected_idx = min(len(backups) - 1, selected_idx + 1)
                elif key.name == 'KEY_ENTER' or key == '\n' or key == '\r':
                    selected = backups[selected_idx]
                    print(term.green(f'\n✅ Selected: {selected.name}'))
                    return selected
                elif key.lower() == 'q' or key.name == 'KEY_ESCAPE':
                    print(term.yellow('\n⚠️  Selection cancelled'))
                    return None


def _simple_select_local_backup(backups: List[Path]) -> Optional[Path]:
    """Simple fallback selector when blessed is not available."""
    print('\n✨ Available Local Backups\n')
    print('─' * 80)

    for i, backup_file in enumerate(backups):
        size_mb = backup_file.stat().st_size / (1024 * 1024)
        mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
        age = format_backup_age(mtime)

        if i == 0:
            print(f'  [{i+1}] {backup_file.name:<50} {format_backup_size(size_mb):>10}  ({age}) ⭐ (latest)')
        else:
            print(f'  [{i+1}] {backup_file.name:<50} {format_backup_size(size_mb):>10}  ({age})')

    print('─' * 80)
    print('\n  [Enter] Select latest  [q] Quit\n')

    choice = input('→ Enter your selection (default: latest): ').strip()

    if choice.lower() == 'q':
        print('\n⚠️  Selection cancelled')
        return None

    if not choice:  # Default to latest
        selected = backups[0]
        print(f'\n✅ Selected: {selected.name}')
        return selected

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(backups):
            selected = backups[idx]
            print(f'\n✅ Selected: {selected.name}')
            return selected
        else:
            print(f'❌ Invalid selection. Please choose 1-{len(backups)}')
            return None
    except ValueError:
        print('❌ Invalid input')
        return None


def select_s3_backup(backups: List[S3BackupInfo], environment: str) -> Optional[S3BackupInfo]:
    """Interactive selector for S3 backups with arrow key navigation."""
    if not backups:
        logger.error(f'No backups available to select from in {environment}')
        return None

    if not BLESSED_AVAILABLE:
        # Fallback to simple selection if blessed is not available
        return _simple_select_s3_backup(backups, environment)

    selected_idx = 0  # Default to latest (first) backup

    with term.fullscreen():
        with term.cbreak():
            while True:
                print(term.clear())
                print(term.bold(term.green(f'✨ Available {environment.upper()} Backups\n')))
                print(term.cyan('Use ↑/↓ arrows to navigate, Enter to select, q to quit'))
                print(term.cyan('─' * 100))

                for i, backup_info in enumerate(backups):
                    age = format_backup_age(backup_info.last_modified)
                    timestamp = backup_info.last_modified.strftime('%Y-%m-%d %H:%M')

                    # Add cache indicator
                    cache_indicator = ' 💾' if backup_info.is_cached else ''

                    line = f'  {backup_info.filename:<45} {format_backup_size(backup_info.size_mb):>10}  {timestamp}  ({age}){cache_indicator}'

                    if i == selected_idx:
                        # Highlight selected item
                        if i == 0:
                            print(term.reverse(term.bright_white(f'→ {line} ⭐')))
                        else:
                            print(term.reverse(f'→ {line}'))
                    else:
                        # Normal display
                        if i == 0:
                            print(term.bright_white(f'  {line} ⭐'))
                        else:
                            print(f'  {line}')

                print(term.cyan('─' * 100))
                print(
                    f"\n{term.yellow('[↑/↓]')} Navigate  {term.green('[Enter]')} Select  {term.red('[q/Esc]')} Cancel  "
                    f"{term.blue('💾 = Cached locally')}"
                )

                # Get key input
                key = term.inkey()

                if key.name == 'KEY_UP':
                    selected_idx = max(0, selected_idx - 1)
                elif key.name == 'KEY_DOWN':
                    selected_idx = min(len(backups) - 1, selected_idx + 1)
                elif key.name == 'KEY_ENTER' or key == '\n' or key == '\r':
                    selected = backups[selected_idx]
                    print(term.green(f'\n✅ Selected: {selected.filename}'))
                    return selected
                elif key.lower() == 'q' or key.name == 'KEY_ESCAPE':
                    print(term.yellow('\n⚠️  Selection cancelled'))
                    return None


def _simple_select_s3_backup(backups: List[S3BackupInfo], environment: str) -> Optional[S3BackupInfo]:
    """Simple fallback selector when blessed is not available."""
    print(f'\n✨ Available {environment.upper()} Backups\n')
    print('─' * 100)

    for i, backup_info in enumerate(backups):
        age = format_backup_age(backup_info.last_modified)
        timestamp = backup_info.last_modified.strftime('%Y-%m-%d %H:%M')
        cache_indicator = ' 💾' if backup_info.is_cached else ''

        if i == 0:
            print(
                f'  [{i+1}] {backup_info.filename:<45} {format_backup_size(backup_info.size_mb):>10}  {timestamp}  ({age}) ⭐ (latest){cache_indicator}'
            )
        else:
            print(
                f'  [{i+1}] {backup_info.filename:<45} {format_backup_size(backup_info.size_mb):>10}  {timestamp}  ({age}){cache_indicator}'
            )

    print('─' * 100)
    print('\n  [Enter] Select latest  [q] Quit  💾 = Cached locally\n')

    choice = input('→ Enter your selection (default: latest): ').strip()

    if choice.lower() == 'q':
        print('\n⚠️  Selection cancelled')
        return None

    if not choice:  # Default to latest
        selected = backups[0]
        print(f'\n✅ Selected: {selected.filename}')
        return selected

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(backups):
            selected = backups[idx]
            print(f'\n✅ Selected: {selected.filename}')
            return selected
        else:
            print(f'❌ Invalid selection. Please choose 1-{len(backups)}')
            return None
    except ValueError:
        print('❌ Invalid input')
        return None


def confirm_restore(backup_name: str, database_name: str) -> bool:
    """Interactive confirmation for restore operation."""
    print(term.bold(term.yellow('\n⚠️  WARNING: Database Restore Operation')))
    print(term.yellow('─' * 50))
    print('\nThis will:')
    print(f"  • {term.red('DROP')} the existing database: {term.bold(database_name)}")
    print(f"  • {term.green('RESTORE')} from backup: {term.bold(backup_name)}")
    print(term.yellow('─' * 50))

    while True:
        response = input(term.bold('\n→ Are you sure you want to continue? [Y/n]: ')).strip().lower()

        # Default to yes if user just presses Enter
        if response == '' or response in ['yes', 'y']:
            return True
        elif response in ['no', 'n', 'q']:
            print(term.yellow('\n⚠️  Restore cancelled'))
            return False
        else:
            print(term.red("Please answer 'yes' or 'no' (or press Enter for yes)"))
