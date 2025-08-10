#!/usr/bin/env python3
"""
Idle Stuff - Core Game Loop Framework
A modular idle game with procedural entities and extensible architecture.
"""

import time
import json
import sqlite3
import random
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod
import os


# =============================================================================
# CORE GAME DATA STRUCTURES
# =============================================================================

@dataclass
class EntityTraits:
    """Core traits that affect entity performance"""
    efficiency: float = 1.0
    learning_rate: float = 0.1
    cooperation: float = 1.0
    stamina: float = 1.0

@dataclass
class Entity:
    """A procedurally generated worker entity"""
    id: str
    name: str
    entity_type: str  # gatherer, philosopher, caretaker, builder, defender
    traits: EntityTraits
    experience: Dict[str, float]  # task -> experience level
    current_task: Optional[str] = None

@dataclass
class Resource:
    """A game resource"""
    name: str
    amount: float = 0.0
    production_rate: float = 0.0

@dataclass
class GameState:
    """Complete game state"""
    tick: int = 0
    resources: Dict[str, Resource] = None
    entities: Dict[str, Entity] = None
    technologies: List[str] = None
    prestige_tokens: int = 0
    player_boost: float = 1.0
    
    def __post_init__(self):
        if self.resources is None:
            self.resources = {}
        if self.entities is None:
            self.entities = {}
        if self.technologies is None:
            self.technologies = []


# =============================================================================
# PERSISTENCE MODULE
# =============================================================================

class GameDatabase:
    """SQLite persistence layer for game state"""
    
    def __init__(self, db_path: str = "idle_stuff.db"):
        self.db_path = db_path
        self.connection = None
        self._initialize_database()
    
    def _initialize_database(self):
        """Create database tables if they don't exist"""
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row  # Enable dict-like access
        
        cursor = self.connection.cursor()
        
        # Game state table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS game_state (
                id INTEGER PRIMARY KEY,
                tick INTEGER,
                prestige_tokens INTEGER,
                player_boost REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Resources table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS resources (
                game_id INTEGER,
                name TEXT,
                amount REAL,
                production_rate REAL,
                FOREIGN KEY (game_id) REFERENCES game_state(id),
                PRIMARY KEY (game_id, name)
            )
        ''')
        
        # Entities table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS entities (
                game_id INTEGER,
                entity_id TEXT,
                name TEXT,
                entity_type TEXT,
                current_task TEXT,
                efficiency REAL,
                learning_rate REAL,
                cooperation REAL,
                stamina REAL,
                FOREIGN KEY (game_id) REFERENCES game_state(id),
                PRIMARY KEY (game_id, entity_id)
            )
        ''')
        
        # Entity experience table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS entity_experience (
                game_id INTEGER,
                entity_id TEXT,
                task_type TEXT,
                experience REAL,
                FOREIGN KEY (game_id) REFERENCES game_state(id),
                PRIMARY KEY (game_id, entity_id, task_type)
            )
        ''')
        
        # Technologies table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS technologies (
                game_id INTEGER,
                tech_name TEXT,
                unlocked_at INTEGER,
                FOREIGN KEY (game_id) REFERENCES game_state(id),
                PRIMARY KEY (game_id, tech_name)
            )
        ''')
        
        self.connection.commit()
    
    def save_game_state(self, state: GameState) -> int:
        """Save complete game state, returns game_id"""
        cursor = self.connection.cursor()
        
        # Insert or update game state
        cursor.execute('''
            INSERT OR REPLACE INTO game_state (id, tick, prestige_tokens, player_boost, updated_at)
            VALUES (1, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (state.tick, state.prestige_tokens, state.player_boost))
        
        game_id = 1  # For now, single save slot
        
        # Clear existing data for this game
        cursor.execute('DELETE FROM resources WHERE game_id = ?', (game_id,))
        cursor.execute('DELETE FROM entities WHERE game_id = ?', (game_id,))
        cursor.execute('DELETE FROM entity_experience WHERE game_id = ?', (game_id,))
        cursor.execute('DELETE FROM technologies WHERE game_id = ?', (game_id,))
        
        # Save resources
        for resource in state.resources.values():
            cursor.execute('''
                INSERT INTO resources (game_id, name, amount, production_rate)
                VALUES (?, ?, ?, ?)
            ''', (game_id, resource.name, resource.amount, resource.production_rate))
        
        # Save entities
        for entity in state.entities.values():
            cursor.execute('''
                INSERT INTO entities (
                    game_id, entity_id, name, entity_type, current_task,
                    efficiency, learning_rate, cooperation, stamina
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                game_id, entity.id, entity.name, entity.entity_type, entity.current_task,
                entity.traits.efficiency, entity.traits.learning_rate,
                entity.traits.cooperation, entity.traits.stamina
            ))
            
            # Save entity experience
            for task_type, experience in entity.experience.items():
                cursor.execute('''
                    INSERT INTO entity_experience (game_id, entity_id, task_type, experience)
                    VALUES (?, ?, ?, ?)
                ''', (game_id, entity.id, task_type, experience))
        
        # Save technologies
        for tech in state.technologies:
            cursor.execute('''
                INSERT INTO technologies (game_id, tech_name, unlocked_at)
                VALUES (?, ?, ?)
            ''', (game_id, tech, state.tick))
        
        self.connection.commit()
        return game_id
    
    def load_game_state(self, game_id: int = 1) -> Optional[GameState]:
        """Load game state from database"""
        cursor = self.connection.cursor()
        
        # Load basic game state
        cursor.execute('SELECT * FROM game_state WHERE id = ?', (game_id,))
        game_row = cursor.fetchone()
        
        if not game_row:
            return None
        
        # Create base game state
        state = GameState(
            tick=game_row['tick'],
            prestige_tokens=game_row['prestige_tokens'],
            player_boost=game_row['player_boost']
        )
        
        # Load resources
        cursor.execute('SELECT * FROM resources WHERE game_id = ?', (game_id,))
        for row in cursor.fetchall():
            resource = Resource(
                name=row['name'],
                amount=row['amount'],
                production_rate=row['production_rate']
            )
            state.resources[resource.name] = resource
        
        # Load entities
        cursor.execute('SELECT * FROM entities WHERE game_id = ?', (game_id,))
        for row in cursor.fetchall():
            traits = EntityTraits(
                efficiency=row['efficiency'],
                learning_rate=row['learning_rate'],
                cooperation=row['cooperation'],
                stamina=row['stamina']
            )
            
            entity = Entity(
                id=row['entity_id'],
                name=row['name'],
                entity_type=row['entity_type'],
                traits=traits,
                experience={},
                current_task=row['current_task']
            )
            
            # Load entity experience
            exp_cursor = self.connection.cursor()
            exp_cursor.execute('''
                SELECT task_type, experience FROM entity_experience 
                WHERE game_id = ? AND entity_id = ?
            ''', (game_id, entity.id))
            
            for exp_row in exp_cursor.fetchall():
                entity.experience[exp_row['task_type']] = exp_row['experience']
            
            state.entities[entity.id] = entity
        
        # Load technologies
        cursor.execute('SELECT tech_name FROM technologies WHERE game_id = ?', (game_id,))
        state.technologies = [row['tech_name'] for row in cursor.fetchall()]
        
        return state
    
    def game_exists(self, game_id: int = 1) -> bool:
        """Check if a saved game exists"""
        cursor = self.connection.cursor()
        cursor.execute('SELECT COUNT(*) FROM game_state WHERE id = ?', (game_id,))
        return cursor.fetchone()[0] > 0
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()


# =============================================================================
# GAME LOGIC MODULE
# =============================================================================

class GameLogic:
    """Core game logic, separate from I/O and display"""
    
    def __init__(self, database: Optional[GameDatabase] = None):
        self.database = database or GameDatabase()
        self.state = GameState()
        self.auto_save_interval = 10  # Save every 10 ticks
        self._initialize_or_load_game()
    
    def _initialize_or_load_game(self):
        """Load existing game or create new one"""
        if self.database.game_exists():
            loaded_state = self.database.load_game_state()
            if loaded_state:
                self.state = loaded_state
                print(f"Loaded existing game at tick {self.state.tick}")
                return
        
        # Create new game
        print("Starting new game...")
        self._initialize_base_game()
        self.save_game()
    
    def save_game(self):
        """Save current game state"""
        if self.database:
            self.database.save_game_state(self.state)
    
    def _initialize_base_game(self):
        """Set up starting conditions"""
        # Start with basic resource
        self.state.resources["energy"] = Resource("energy", amount=10.0)
        
        # Generate starting entities
        for i in range(3):
            entity = self._generate_entity(f"entity_{i}", "gatherer")
            self.state.entities[entity.id] = entity
    
    def _generate_entity(self, entity_id: str, entity_type: str) -> Entity:
        """Generate a procedural entity"""
        names = ["Zara", "Kael", "Luna", "Orion", "Nova", "Sage", "Echo", "Zen"]
        
        # Procedural traits with some randomization
        traits = EntityTraits(
            efficiency=random.uniform(0.8, 1.2),
            learning_rate=random.uniform(0.05, 0.15),
            cooperation=random.uniform(0.9, 1.1),
            stamina=random.uniform(0.8, 1.2)
        )
        
        return Entity(
            id=entity_id,
            name=random.choice(names),
            entity_type=entity_type,
            traits=traits,
            experience={"gathering": 0.0},
            current_task="gathering"
        )
    
    def tick(self) -> Dict[str, Any]:
        """Execute one game tick - returns events for display"""
        self.state.tick += 1
        events = []
        
        # Process entity actions
        for entity in self.state.entities.values():
            event = self._process_entity_action(entity)
            if event:
                events.append(event)
        
        # Update resource production rates
        self._update_production_rates()
        
        # Apply resource production
        for resource in self.state.resources.values():
            if resource.production_rate > 0:
                resource.amount += resource.production_rate
        
        # Auto-save periodically
        if self.state.tick % self.auto_save_interval == 0:
            self.save_game()
            events.append({
                "type": "system",
                "message": "Game auto-saved"
            })
        
        return {
            "tick": self.state.tick,
            "events": events,
            "resources": {name: r.amount for name, r in self.state.resources.items()},
            "production_rates": {name: r.production_rate for name, r in self.state.resources.items()},
            "entities": {eid: self._entity_to_dict(entity) for eid, entity in self.state.entities.items()}
        }
    
    def _entity_to_dict(self, entity: Entity) -> Dict[str, Any]:
        """Convert entity to dictionary for display"""
        return {
            "id": entity.id,
            "name": entity.name,
            "type": entity.entity_type,
            "task": entity.current_task or "idle",
            "efficiency": entity.traits.efficiency,
            "experience": sum(entity.experience.values()),
            "traits": asdict(entity.traits)
        }
    
    def _process_entity_action(self, entity: Entity) -> Optional[Dict[str, Any]]:
        """Process a single entity's action for this tick"""
        if entity.current_task == "gathering":
            # Calculate efficiency based on traits and experience
            base_gathering = 1.0
            efficiency_mult = entity.traits.efficiency
            experience_mult = 1.0 + (entity.experience.get("gathering", 0) * 0.1)
            
            gathered = base_gathering * efficiency_mult * experience_mult
            
            # Add to energy resource
            if "energy" in self.state.resources:
                self.state.resources["energy"].amount += gathered
            
            # Gain experience
            entity.experience["gathering"] = entity.experience.get("gathering", 0) + entity.traits.learning_rate
            
            # Occasional event for interest
            if random.random() < 0.05:  # 5% chance
                return {
                    "type": "discovery",
                    "entity": entity.name,
                    "message": f"{entity.name} found an efficient energy source!"
                }
        
        return None
    
    def _update_production_rates(self):
        """Update production rates based on current state"""
        # For now, production rate is just sum of active gatherers
        gatherers = [e for e in self.state.entities.values() 
                    if e.entity_type == "gatherer" and e.current_task == "gathering"]
        
        energy_rate = sum(e.traits.efficiency * (1.0 + e.experience.get("gathering", 0) * 0.1) 
                         for e in gatherers)
        
        if "energy" in self.state.resources:
            self.state.resources["energy"].production_rate = energy_rate
    
    def apply_player_boost(self, entity_id: str, boost_multiplier: float = 2.0):
        """Apply manual player boost to an entity"""
        if entity_id in self.state.entities:
            entity = self.state.entities[entity_id]
            if entity.current_task == "gathering":
                boosted_amount = boost_multiplier * entity.traits.efficiency
                if "energy" in self.state.resources:
                    self.state.resources["energy"].amount += boosted_amount
                return f"Boosted {entity.name} for +{boosted_amount:.1f} energy!"
        return "Boost failed!"
    
    def get_game_state(self) -> GameState:
        """Get current game state (for saving/display)"""
        return self.state


# =============================================================================
# DISPLAY MODULE (Abstract)
# =============================================================================

class Display(ABC):
    """Abstract display interface - allows for ncurses, GUI, web, etc."""
    
    @abstractmethod
    def render(self, game_data: Dict[str, Any]):
        """Render the current game state"""
        pass
    
    @abstractmethod
    def get_input(self) -> Optional[str]:
        """Get player input (non-blocking)"""
        pass
    
    @abstractmethod
    def cleanup(self):
        """Cleanup display resources"""
        pass


# =============================================================================
# BASIC CONSOLE DISPLAY (Placeholder for ncurses)
# =============================================================================

class ConsoleDisplay(Display):
    """Simple console display for testing"""
    
    def render(self, game_data: Dict[str, Any]):
        print(f"\n--- Tick {game_data['tick']} ---")
        print("Resources:")
        for name, amount in game_data['resources'].items():
            rate = game_data['production_rates'].get(name, 0)
            print(f"  {name}: {amount:.1f} (+{rate:.2f}/tick)")
        
        if game_data['events']:
            print("Events:")
            for event in game_data['events']:
                print(f"  • {event['message']}")
    
    def get_input(self) -> Optional[str]:
        # Non-blocking input would be implemented here
        return None
    
    def cleanup(self):
        pass


# =============================================================================
# MAIN GAME LOOP
# =============================================================================

class IdleStuffGame:
    """Main game controller"""
    
    def __init__(self, display: Display, database: Optional[GameDatabase] = None):
        self.database = database or GameDatabase()
        self.logic = GameLogic(self.database)
        self.display = display
        self.running = False
        self.tick_rate = 1.0  # seconds per tick
        self.last_boost_message = ""
    
    def run(self):
        """Main game loop with interactive controls"""
        self.running = True
        
        try:
            while self.running:
                # Process game tick
                tick_data = self.logic.tick()
                
                # Add boost message to events if present
                if self.last_boost_message:
                    tick_data['events'].append({
                        'type': 'player',
                        'message': self.last_boost_message
                    })
                    self.last_boost_message = ""
                
                # Render display
                self.display.render(tick_data)
                
                # Handle player input
                self._handle_input()
                
                # Wait for next tick
                time.sleep(self.tick_rate)
                
        except KeyboardInterrupt:
            self.running = False
        finally:
            self._shutdown()
    
    def _handle_input(self):
        """Process player input commands"""
        cmd = self.display.get_input()
        
        if not cmd:
            return
        
        if cmd == "quit":
            self.running = False
        elif cmd == "save":
            self.logic.save_game()
            self.last_boost_message = "Game saved manually!"
        elif cmd.startswith("boost:"):
            entity_id = cmd.split(":", 1)[1]
            result = self.logic.apply_player_boost(entity_id)
            self.last_boost_message = result
        elif cmd == "speed_up":
            self.tick_rate = max(0.1, self.tick_rate * 0.8)
            self.last_boost_message = f"Game speed increased (tick: {self.tick_rate:.1f}s)"
        elif cmd == "speed_down":
            self.tick_rate = min(5.0, self.tick_rate * 1.25)
            self.last_boost_message = f"Game speed decreased (tick: {self.tick_rate:.1f}s)"
        elif cmd == "reset":
            self.last_boost_message = "Selection reset"
    
    def _shutdown(self):
        """Clean shutdown with save"""
        self.logic.save_game()
        self.display.cleanup()
        self.database.close()


# =============================================================================
# TESTING & DEMO
# =============================================================================

def run_with_ncurses():
    """Run the game with ncurses display"""
    try:
        # Import ncurses display
        from ncurses_display import NCursesGameInterface
        
        with NCursesGameInterface() as display:
            game = IdleStuffGame(display)
            game.run()
            
    except ImportError:
        print("ncurses_display module not found. Using console display.")
        run_with_console()
    except Exception as e:
        print(f"Error initializing ncurses: {e}")
        print("Falling back to console display.")
        run_with_console()

def run_with_console():
    """Run the game with simple console display"""
    display = ConsoleDisplay()
    game = IdleStuffGame(display)
    print("Idle Stuff starting...")
    print("Press Ctrl+C to quit")
    game.run()

if __name__ == "__main__":
    # Try ncurses first, fall back to console
    run_with_ncurses()

