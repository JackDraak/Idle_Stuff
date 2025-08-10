#!/usr/bin/env python3
"""
Idle Stuff - Ncurses Display Module
Terminal-based UI with real-time updates and interactive controls.
"""

import curses
import time
import threading
import queue
from collections import deque


class NCursesDisplay:
    """Ncurses-based display with real-time updates and input handling"""
    
    def __init__(self):
        self.stdscr = None
        self.windows = {}
        self.colors_initialized = False
        self.event_log = deque(maxlen=20)  # Keep last 20 events
        self.input_queue = queue.Queue()
        self.current_selection = 0
        self.selectable_items = []  # List of (type, id, description) tuples
        
        # Display dimensions (calculated on init)
        self.height = 0
        self.width = 0
        
        # Window layouts
        self.layouts = {
            'header': {'y': 0, 'height': 3},
            'resources': {'y': 3, 'height': 8},
            'entities': {'y': 11, 'height': 12},
            'events': {'y': 23, 'height': 8},
            'controls': {'y': 31, 'height': 4}
        }
    
    def initialize(self):
        """Initialize ncurses"""
        self.stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        self.stdscr.keypad(True)
        self.stdscr.nodelay(True)  # Non-blocking input
        curses.curs_set(0)  # Hide cursor
        
        # Get screen dimensions
        self.height, self.width = self.stdscr.getmaxyx()
        
        # Initialize colors if supported
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            
            # Define color pairs
            curses.init_pair(1, curses.COLOR_GREEN, -1)    # Success/positive
            curses.init_pair(2, curses.COLOR_YELLOW, -1)   # Warning/highlight
            curses.init_pair(3, curses.COLOR_RED, -1)      # Error/negative
            curses.init_pair(4, curses.COLOR_BLUE, -1)     # Info
            curses.init_pair(5, curses.COLOR_CYAN, -1)     # Entity names
            curses.init_pair(6, curses.COLOR_MAGENTA, -1)  # Resources
            curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_BLUE)  # Selected
            
            self.colors_initialized = True
        
        # Create windows
        self._create_windows()
        
        # Start input handler thread
        self.input_thread = threading.Thread(target=self._input_handler, daemon=True)
        self.input_thread.start()
    
    def _create_windows(self):
        """Create all display windows"""
        # Adjust layouts based on screen size
        if self.height < 35:
            # Compact layout for smaller terminals
            self.layouts = {
                'header': {'y': 0, 'height': 2},
                'resources': {'y': 2, 'height': 6},
                'entities': {'y': 8, 'height': 8},
                'events': {'y': 16, 'height': 6},
                'controls': {'y': 22, 'height': 3}
            }
        
        for name, layout in self.layouts.items():
            height = min(layout['height'], self.height - layout['y'] - 1)
            width = self.width - 2
            if height > 0 and width > 0:
                self.windows[name] = curses.newwin(height, width, layout['y'], 1)
                self.windows[name].box()
    
    def _input_handler(self):
        """Handle keyboard input in separate thread"""
        while True:
            try:
                key = self.stdscr.getch()
                if key != -1:  # Valid key pressed
                    self.input_queue.put(key)
                time.sleep(0.05)  # Small delay to prevent CPU spinning
            except:
                break
    
    def render(self, game_data):
        """Render complete game state"""
        try:
            # Clear all windows
            for window in self.windows.values():
                window.clear()
                window.box()
            
            # Update selectable items
            self._update_selectable_items(game_data)
            
            # Render each section
            self._render_header(game_data)
            self._render_resources(game_data)
            self._render_entities(game_data)
            self._render_events(game_data)
            self._render_controls()
            
            # Refresh all windows
            for window in self.windows.values():
                window.refresh()
            
            self.stdscr.refresh()
            
        except curses.error:
            # Handle terminal resize or other display errors gracefully
            pass
    
    def _update_selectable_items(self, game_data):
        """Update list of items player can interact with"""
        self.selectable_items = []
        
        entities = game_data.get('entities', {})
        for entity_id, entity_data in entities.items():
            name = entity_data.get('name', entity_id)
            entity_type = entity_data.get('type', 'unknown')
            self.selectable_items.append(('boost', entity_id, f"Boost {name} ({entity_type})"))
        
        # Ensure selection is within bounds
        if self.current_selection >= len(self.selectable_items):
            self.current_selection = max(0, len(self.selectable_items) - 1)
    
    def _render_header(self, game_data):
        """Render game title and basic info"""
        if 'header' not in self.windows:
            return
        
        win = self.windows['header']
        
        # Title
        title = "IDLE STUFF"
        win.addstr(1, (self.width - len(title)) // 2, title, 
                  curses.color_pair(2) | curses.A_BOLD if self.colors_initialized else curses.A_BOLD)
        
        # Tick counter
        tick_info = f"Tick: {game_data.get('tick', 0)}"
        win.addstr(1, self.width - len(tick_info) - 5, tick_info, 
                  curses.color_pair(4) if self.colors_initialized else 0)
    
    def _render_resources(self, game_data):
        """Render resources panel"""
        if 'resources' not in self.windows:
            return
        
        win = self.windows['resources']
        
        # Section title
        win.addstr(0, 2, " RESOURCES ", curses.color_pair(6) | curses.A_BOLD if self.colors_initialized else curses.A_BOLD)
        
        resources = game_data.get('resources', {})
        production_rates = game_data.get('production_rates', {})
        
        row = 2
        for name, amount in resources.items():
            if row >= win.getmaxyx()[0] - 1:
                break
            
            rate = production_rates.get(name, 0)
            
            # Resource name
            win.addstr(row, 2, f"{name.capitalize()}:", 
                      curses.color_pair(6) if self.colors_initialized else 0)
            
            # Amount
            amount_str = f"{amount:.1f}"
            win.addstr(row, 15, amount_str, 
                      curses.color_pair(1) if self.colors_initialized else 0)
            
            # Production rate
            if rate > 0:
                rate_str = f"(+{rate:.2f}/tick)"
                win.addstr(row, 25, rate_str, 
                          curses.color_pair(2) if self.colors_initialized else 0)
            
            row += 1
        
        # Add some usage stats
        if row < win.getmaxyx()[0] - 2:
            win.addstr(row + 1, 2, "─" * (self.width - 6))
            win.addstr(row + 2, 2, f"Total Resources: {len(resources)}", 
                      curses.color_pair(4) if self.colors_initialized else 0)
    
    def _render_entities(self, game_data):
        """Render entities panel"""
        if 'entities' not in self.windows:
            return
        
        win = self.windows['entities']
        
        # Section title
        win.addstr(0, 2, " ENTITIES ", curses.color_pair(5) | curses.A_BOLD if self.colors_initialized else curses.A_BOLD)
        
        entities = game_data.get('entities', {})
        
        row = 2
        entity_list = list(entities.items())
        
        for i, (entity_id, entity_data) in enumerate(entity_list):
            if row >= win.getmaxyx()[0] - 1:
                break
            
            # Highlight if selected
            attr = 0
            if self.current_selection == i and self.colors_initialized:
                attr = curses.color_pair(7)
            if self.current_selection == i:
                attr |= curses.A_REVERSE
            
            # Entity info line
            name = entity_data.get('name', entity_id)
            entity_type = entity_data.get('type', 'unknown')
            task = entity_data.get('task', 'idle')
            info_line = f"{name} ({entity_type}) - {task}"
            
            win.addstr(row, 2, info_line[:self.width-6], attr)
            
            # Stats line
            if row + 1 < win.getmaxyx()[0] - 1:
                efficiency = entity_data.get('efficiency', 1.0)
                experience = entity_data.get('experience', 0.0)
                stats_line = f"  Eff: {efficiency:.1f} | Exp: {experience:.1f}"
                win.addstr(row + 1, 2, stats_line, 
                          curses.color_pair(4) if self.colors_initialized else 0)
            
            row += 3
        
        # Controls hint
        if row < win.getmaxyx()[0] - 2:
            win.addstr(row, 2, "↑↓: Select | SPACE: Boost", 
                      curses.color_pair(2) if self.colors_initialized else 0)
    
    def _render_events(self, game_data):
        """Render events log"""
        if 'events' not in self.windows:
            return
        
        win = self.windows['events']
        
        # Section title
        win.addstr(0, 2, " EVENTS ", curses.color_pair(4) | curses.A_BOLD if self.colors_initialized else curses.A_BOLD)
        
        # Add new events to log
        for event in game_data.get('events', []):
            if event.get('type') == 'discovery':
                self.event_log.append(f"🔍 {event['message']}")
            elif event.get('type') == 'system':
                self.event_log.append(f"💾 {event['message']}")
            else:
                self.event_log.append(f"• {event.get('message', str(event))}")
        
        # Display recent events
        row = 2
        max_rows = win.getmaxyx()[0] - 3
        
        for event in list(self.event_log)[-max_rows:]:
            if row >= win.getmaxyx()[0] - 1:
                break
            
            # Truncate long messages
            display_event = event[:self.width-6] if len(event) > self.width-6 else event
            
            # Color code different event types
            attr = 0
            if '🔍' in event:
                attr = curses.color_pair(1) if self.colors_initialized else 0
            elif '💾' in event:
                attr = curses.color_pair(4) if self.colors_initialized else 0
            
            win.addstr(row, 2, display_event, attr)
            row += 1
    
    def _render_controls(self):
        """Render controls help"""
        if 'controls' not in self.windows:
            return
        
        win = self.windows['controls']
        
        # Section title
        win.addstr(0, 2, " CONTROLS ", curses.color_pair(2) | curses.A_BOLD if self.colors_initialized else curses.A_BOLD)
        
        controls = [
            "↑↓: Navigate | SPACE: Boost Entity | S: Save Game | Q: Quit",
            "R: Reset Selection | +/-: Adjust Game Speed"
        ]
        
        row = 1
        for control_line in controls:
            if row < win.getmaxyx()[0] - 1:
                win.addstr(row, 2, control_line[:self.width-6])
                row += 1
    
    def get_input(self):
        """Get player input (non-blocking)"""
        try:
            key = self.input_queue.get_nowait()
            
            # Handle navigation
            if key == curses.KEY_UP:
                self.current_selection = max(0, self.current_selection - 1)
                return "nav_up"
            elif key == curses.KEY_DOWN:
                self.current_selection = min(len(self.selectable_items) - 1, self.current_selection + 1)
                return "nav_down"
            elif key == ord(' '):  # Spacebar
                if 0 <= self.current_selection < len(self.selectable_items):
                    item = self.selectable_items[self.current_selection]
                    return f"boost:{item[1]}"  # Return boost:entity_id
                return "boost"
            elif key == ord('s') or key == ord('S'):
                return "save"
            elif key == ord('q') or key == ord('Q'):
                return "quit"
            elif key == ord('r') or key == ord('R'):
                self.current_selection = 0
                return "reset"
            elif key == ord('+') or key == ord('='):
                return "speed_up"
            elif key == ord('-'):
                return "speed_down"
            
        except queue.Empty:
            pass
        
        return None
    
    def cleanup(self):
        """Cleanup ncurses resources"""
        if self.stdscr:
            curses.nocbreak()
            self.stdscr.keypad(False)
            curses.echo()
            curses.endwin()
    
    def show_message(self, message: str, duration: float = 2.0):
        """Show a temporary message overlay"""
        if not self.stdscr:
            return
        
        # Create message window
        msg_height = 5
        msg_width = min(len(message) + 4, self.width - 4)
        msg_y = (self.height - msg_height) // 2
        msg_x = (self.width - msg_width) // 2
        
        msg_win = curses.newwin(msg_height, msg_width, msg_y, msg_x)
        msg_win.box()
        
        # Display message
        msg_win.addstr(2, 2, message[:msg_width-4], 
                      curses.color_pair(2) | curses.A_BOLD if self.colors_initialized else curses.A_BOLD)
        msg_win.refresh()
        
        # Keep displayed for duration
        time.sleep(duration)
        
        # Clean up
        msg_win.clear()
        msg_win.refresh()
        del msg_win


# =============================================================================
# INTEGRATION HELPER
# =============================================================================

class NCursesGameInterface:
    """Wrapper to integrate NCursesDisplay with the main game"""
    
    def __init__(self):
        self.display = NCursesDisplay()
        self.initialized = False
    
    def __enter__(self):
        self.display.initialize()
        self.initialized = True
        return self.display
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.display.cleanup()
        if exc_type:
            print(f"Game ended with error: {exc_val}")
        else:
            print("Game ended normally.")


# =============================================================================
# DEMO/TEST CODE
# =============================================================================

if __name__ == "__main__":
    # Test the ncurses display
    import random
    
    def generate_test_data(tick):
        return {
            'tick': tick,
            'resources': {
                'energy': 156.7 + random.uniform(-10, 10),
                'knowledge': 23.4 + random.uniform(-5, 5)
            },
            'production_rates': {
                'energy': 12.3 + random.uniform(-2, 2),
                'knowledge': 1.7 + random.uniform(-0.5, 0.5)
            },
            'events': [
                {'type': 'discovery', 'message': 'Found efficient energy source!'},
                {'type': 'system', 'message': 'Auto-saved game'}
            ] if tick % 10 == 0 else []
        }
    
    # Test the display
    with NCursesGameInterface() as display:
        tick = 0
        try:
            while True:
                # Generate test data
                game_data = generate_test_data(tick)
                
                # Render
                display.render(game_data)
                
                # Handle input
                cmd = display.get_input()
                if cmd == "quit":
                    break
                elif cmd and cmd.startswith("boost:"):
                    entity_id = cmd.split(":")[1]
                    display.show_message(f"Boosted {entity_id}!")
                
                # Advance tick
                tick += 1
                time.sleep(0.5)  # Slower for demo
                
        except KeyboardInterrupt:
            pass

