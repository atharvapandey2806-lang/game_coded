import random
import json
import os
import hashlib
import uuid
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

# ============================================
# PREMIUM FEATURES & MONETIZATION ENGINE
# ============================================

class Achievement:
    """Achievement/Badge System"""
    def __init__(self, id: str, name: str, description: str, icon: str, requirement: dict):
        self.id = id
        self.name = name
        self.description = description
        self.icon = icon
        self.requirement = requirement

class UserProfile:
    """Enhanced user profile with premium features"""
    def __init__(self, user_id: str, username: str = None):
        self.user_id = user_id
        self.username = username or f"Player_{user_id[:8]}"
        self.level = 1
        self.exp = 0
        self.coins = 100  # In-game currency
        self.premium_coins = 0  # Real money currency
        self.premium_member = False
        self.premium_expiry = None
        self.created_at = datetime.now().isoformat()
        self.last_login = datetime.now().isoformat()
        self.achievements = []
        self.friends = []
        self.stats = {}
        self.daily_reward_claimed = False
        self.daily_reward_date = None
        self.total_playtime = 0  # in seconds
        self.streaks = {
            'current': 0,
            'best': 0,
            'type': None
        }
    
    def claim_daily_reward(self):
        """Claim daily reward"""
        today = datetime.now().date().isoformat()
        if self.daily_reward_date != today:
            reward = 50 + (self.streaks['current'] * 10)
            self.coins += reward
            self.daily_reward_claimed = True
            self.daily_reward_date = today
            return reward
        return 0
    
    def add_exp(self, amount: int):
        """Add experience and handle leveling"""
        self.exp += amount
        level_threshold = 100 * self.level
        if self.exp >= level_threshold:
            self.level += 1
            self.exp -= level_threshold
            self.coins += 50  # Level up bonus
            return True
        return False
    
    def unlock_achievement(self, achievement_id: str):
        """Unlock an achievement"""
        if achievement_id not in self.achievements:
            self.achievements.append(achievement_id)
            self.coins += 25
            return True
        return False
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'user_id': self.user_id,
            'username': self.username,
            'level': self.level,
            'exp': self.exp,
            'coins': self.coins,
            'premium_coins': self.premium_coins,
            'premium_member': self.premium_member,
            'premium_expiry': self.premium_expiry,
            'created_at': self.created_at,
            'last_login': self.last_login,
            'achievements': self.achievements,
            'friends': self.friends,
            'stats': self.stats,
            'streaks': self.streaks,
            'total_playtime': self.total_playtime
        }

# ============================================
# PLUGIN SYSTEM ARCHITECTURE
# ============================================

class GamePlugin(ABC):
    """Base class for all game plugins with premium features"""
    
    def __init__(self):
        self.name = "Game"
        self.description = "A game"
        self.difficulty_levels = ['easy', 'medium', 'hard']
        self.min_bet = 10  # Minimum coins to wager
        self.max_bet = 500  # Maximum coins to wager
        self.achievements = []
    
    @abstractmethod
    def play(self, user_profile: UserProfile = None, bet_amount: int = 0):
        """Execute the game logic"""
        pass
    
    @abstractmethod
    def get_info(self):
        """Return game information"""
        pass
    
    def calculate_reward(self, base_reward: int, difficulty: str = 'medium', multiplier: float = 1.0) -> int:
        """Calculate reward with difficulty multiplier"""
        multipliers = {'easy': 1.0, 'medium': 1.5, 'hard': 2.5}
        return int(base_reward * multipliers.get(difficulty, 1.5) * multiplier)


class RockPaperScissorsPlugin(GamePlugin):
    """Rock Paper Scissors Game Plugin - Premium Edition"""
    
    def __init__(self):
        super().__init__()
        self.name = "Rock Paper Scissors"
        self.description = "Classic Rock Paper Scissors game - Wager coins for bigger rewards!"
        self.wins = 0
        self.losses = 0
        self.ties = 0
        self.total_winnings = 0
        self.achievements = [
            Achievement('rps_first_win', 'First Victory', 'Win your first RPS match', '🎯', {'wins': 1}),
            Achievement('rps_10_wins', 'Hot Streak', 'Win 10 matches', '🔥', {'wins': 10}),
            Achievement('rps_100_wins', 'Legend', 'Win 100 matches', '👑', {'wins': 100}),
            Achievement('rps_50_streak', 'Unbeatable', 'Win 50 matches in a row', '⚡', {'consecutive_wins': 50}),
        ]
    
    def play(self, user_profile: UserProfile = None, bet_amount: int = 0):
        choices = ['rock', 'paper', 'scissors']
        
        while True:
            print(f"\n💰 Your coins: {user_profile.coins if user_profile else 'N/A'}")
            
            player_choice = input("Enter 'rock', 'paper', 'scissors', or 'quit': ").strip().lower()
            
            if player_choice == 'quit':
                return self.get_stats()
            
            if player_choice not in choices:
                print("❌ Invalid choice!")
                continue
            
            computer_choice = random.choice(choices)
            print(f"\n🎮 You chose: {player_choice}")
            print(f"🤖 Computer chose: {computer_choice}")
            
            result, player_won = self._determine_winner(player_choice, computer_choice)
            print(result)
            
            # Handle rewards
            if player_won and user_profile:
                reward = self.calculate_reward(10, 'medium', 1.0)
                user_profile.coins += reward
                user_profile.add_exp(25)
                self.total_winnings += reward
                print(f"🎉 +{reward} coins | +25 XP")
            elif not player_won and user_profile and bet_amount > 0:
                loss = min(bet_amount, user_profile.coins)
                user_profile.coins -= loss
                print(f"😞 -{loss} coins")
            
            print(f"📊 Stats - W: {self.wins} | L: {self.losses} | T: {self.ties}\n")
            
            play_again = input("Play again? (yes/no): ").strip().lower()
            if play_again != 'yes':
                return self.get_stats()
    
    def _determine_winner(self, player, computer):
        if player == computer:
            self.ties += 1
            return "🤝 It's a tie!", None
        elif (player == 'rock' and computer == 'scissors') or \
             (player == 'paper' and computer == 'rock') or \
             (player == 'scissors' and computer == 'paper'):
            self.wins += 1
            return "🎉 You win!", True
        else:
            self.losses += 1
            return "😞 Computer wins!", False
    
    def get_stats(self):
        win_rate = (self.wins / (self.wins + self.losses) * 100) if (self.wins + self.losses) > 0 else 0
        return {
            'game': self.name,
            'wins': self.wins,
            'losses': self.losses,
            'ties': self.ties,
            'total_winnings': self.total_winnings,
            'win_rate': round(win_rate, 1)
        }
    
    def get_info(self):
        return {
            'name': self.name,
            'description': self.description,
            'code': 'rps',
            'can_bet': True,
            'min_bet': self.min_bet,
            'max_bet': self.max_bet
        }


class GuessTheNumberPlugin(GamePlugin):
    """Guess the Number - Premium Edition with Leaderboards"""
    
    def __init__(self):
        super().__init__()
        self.name = "Guess the Number"
        self.description = "Guess the secret number - Compete on leaderboards!"
        self.wins = 0
        self.total_attempts = 0
        self.best_score = float('inf')
        self.total_earnings = 0
        self.achievements = [
            Achievement('gtn_perfect', 'First Try', 'Guess on first attempt', '🎯', {'best_guess': 1}),
            Achievement('gtn_speedrunner', 'Speed Runner', 'Guess in 2 attempts', '⚡', {'best_guess': 2}),
            Achievement('gtn_lucky', 'Lucky Streak', 'Win 5 times', '🍀', {'wins': 5}),
            Achievement('gtn_expert', 'Number Master', 'Best score on Hard', '👑', {'hard_best': True}),
        ]
    
    def play(self, user_profile: UserProfile = None, bet_amount: int = 0):
        while True:
            difficulty = input("Choose difficulty (easy/medium/hard) or 'quit': ").strip().lower()
            
            if difficulty == 'quit':
                return self.get_stats()
            
            if difficulty not in self.difficulty_levels:
                print("❌ Invalid difficulty!")
                difficulty = 'medium'
            
            secret_number = self._generate_number(difficulty)
            attempts = self._play_round(secret_number, difficulty, user_profile)
            
            if attempts:
                self.wins += 1
                self.total_attempts += attempts
                if attempts < self.best_score:
                    self.best_score = attempts
                
                # Premium reward system
                if user_profile:
                    reward = self.calculate_reward(50, difficulty, 2.0 / attempts)
                    user_profile.coins += reward
                    user_profile.add_exp(50)
                    self.total_earnings += reward
                    print(f"🎉 +{reward} coins | +50 XP")
                
                print(f"📊 Best: {self.best_score} attempts\n")
            
            play_again = input("Play again? (yes/no): ").strip().lower()
            if play_again != 'yes':
                return self.get_stats()
    
    def _generate_number(self, difficulty):
        if difficulty == 'easy':
            return random.randint(1, 50)
        elif difficulty == 'medium':
            return random.randint(1, 100)
        else:
            return random.randint(1, 1000)
    
    def _play_round(self, secret_number, difficulty, user_profile=None):
        attempts = 0
        max_range = {'easy': 50, 'medium': 100, 'hard': 1000}[difficulty]
        
        print(f"\n🎮 I'm thinking of a number between 1 and {max_range}.")
        
        while True:
            try:
                guess = int(input("Take a guess: "))
                
                if guess < 1 or guess > max_range:
                    print(f"❌ Enter a number between 1 and {max_range}.")
                    continue
                
                attempts += 1
                
                if guess == secret_number:
                    print(f"🎉 Correct in {attempts} attempt(s)!")
                    return attempts
                elif guess < secret_number:
                    print("📈 Too low!")
                else:
                    print("📉 Too high!")
            
            except ValueError:
                print("❌ Invalid input!")
    
    def get_stats(self):
        avg_attempts = self.total_attempts / self.wins if self.wins > 0 else 0
        return {
            'game': self.name,
            'wins': self.wins,
            'best_score': self.best_score if self.best_score != float('inf') else 0,
            'average_attempts': round(avg_attempts, 2),
            'total_earnings': self.total_earnings
        }
    
    def get_info(self):
        return {
            'name': self.name,
            'description': self.description,
            'code': 'gtn',
            'can_bet': True
        }


class MathQuizPlugin(GamePlugin):
    """Math Quiz - Premium Edition with Competitive Scoring"""
    
    def __init__(self):
        super().__init__()
        self.name = "Math Quiz"
        self.description = "Master mathematics - Climb the leaderboard!"
        self.correct = 0
        self.wrong = 0
        self.total_earnings = 0
        self.achievements = [
            Achievement('math_perfectionist', 'Perfect Score', '100% accuracy', '💯', {'accuracy': 100}),
            Achievement('math_speed', 'Speed Demon', 'Complete 10 questions in 60 seconds', '⚡', {'speed': True}),
            Achievement('math_master', 'Math Master', 'Get 50 correct answers', '🧮', {'correct': 50}),
            Achievement('math_expert', 'Expert Difficulty', 'Perfect score on Expert', '👑', {'expert_perfect': True}),
        ]
    
    def play(self, user_profile: UserProfile = None, bet_amount: int = 0):
        difficulty = input("Choose difficulty (easy/medium/hard): ").strip().lower() or 'medium'
        num_questions = int(input("How many questions? (default 10): ") or "10")
        
        start_time = datetime.now()
        
        for i in range(num_questions):
            problem, answer = self._generate_problem(difficulty)
            print(f"\n[Question {i+1}/{num_questions}] {problem}")
            
            try:
                user_answer = float(input("Your answer: "))
                if abs(user_answer - answer) < 0.01:
                    print("✅ Correct!")
                    self.correct += 1
                    if user_profile:
                        user_profile.add_exp(15)
                else:
                    print(f"❌ Wrong! The answer is {answer}")
                    self.wrong += 1
            except ValueError:
                print("❌ Invalid input!")
                self.wrong += 1
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        accuracy = (self.correct / num_questions * 100) if num_questions > 0 else 0
        
        if user_profile:
            reward = self.calculate_reward(int(accuracy * 2), difficulty)
            user_profile.coins += reward
            self.total_earnings += reward
            print(f"\n🎉 +{reward} coins")
        
        return self.get_stats()
    
    def _generate_problem(self, difficulty):
        if difficulty == 'easy':
            a, b = random.randint(1, 10), random.randint(1, 10)
            op = random.choice(['+', '-', '*'])
        elif difficulty == 'medium':
            a, b = random.randint(1, 50), random.randint(1, 50)
            op = random.choice(['+', '-', '*', '/'])
        else:
            a, b = random.randint(1, 100), random.randint(1, 100)
            op = random.choice(['+', '-', '*', '/', '**'])
        
        if op == '+':
            return f"{a} + {b} = ?", a + b
        elif op == '-':
            return f"{a} - {b} = ?", a - b
        elif op == '*':
            return f"{a} × {b} = ?", a * b
        elif op == '/':
            return f"{a} ÷ {b} = ?", round(a / b, 2)
        else:
            return f"{a} ^ {b} = ?", a ** b
    
    def get_stats(self):
        total = self.correct + self.wrong
        percentage = (self.correct / total * 100) if total > 0 else 0
        return {
            'game': self.name,
            'correct': self.correct,
            'wrong': self.wrong,
            'percentage': round(percentage, 1),
            'total_earnings': self.total_earnings
        }
    
    def get_info(self):
        return {
            'name': self.name,
            'description': self.description,
            'code': 'mq',
            'competitive': True
        }


class BlackjackPlugin(GamePlugin):
    """Blackjack - High stakes card game"""
    
    def __init__(self):
        super().__init__()
        self.name = "Blackjack"
        self.description = "Beat the dealer in classic Blackjack!"
        self.wins = 0
        self.losses = 0
        self.total_winnings = 0
        self.achievements = [
            Achievement('bj_natural', 'Natural 21', 'Get Blackjack on first hand', '🎰', {'natural_21': True}),
            Achievement('bj_streak', 'Winning Streak', 'Win 5 games in a row', '🔥', {'streak': 5}),
            Achievement('bj_dealer_bust', 'Dealer Buster', 'Make the dealer bust 10 times', '💥', {'dealer_bust': 10}),
        ]
    
    def play(self, user_profile: UserProfile = None, bet_amount: int = 0):
        while True:
            print("\n" + "="*40)
            print("🎰 BLACKJACK 🎰")
            print("="*40)
            
            bet = int(input(f"💰 Enter bet (1-{user_profile.coins if user_profile else 100}): ") or "10")
            
            if user_profile and bet > user_profile.coins:
                print("❌ Insufficient coins!")
                continue
            
            # Deal cards
            player_cards = self._deal_hand()
            dealer_cards = self._deal_hand()
            
            player_score = self._calculate_score(player_cards)
            dealer_showing = dealer_cards[0]
            
            print(f"\n🎮 Your hand: {player_cards} (Score: {player_score})")
            print(f"🤖 Dealer showing: {dealer_showing}")
            
            # Player's turn
            while player_score < 21:
                action = input("Hit (h) or Stand (s)? ").strip().lower()
                if action == 's':
                    break
                elif action == 'h':
                    player_cards.append(random.randint(1, 13))
                    player_score = self._calculate_score(player_cards)
                    print(f"Your hand: {player_cards} (Score: {player_score})")
                    if player_score > 21:
                        print("💣 Bust! You lose!")
                        self.losses += 1
                        break
            
            # Dealer's turn
            if player_score <= 21:
                dealer_score = self._calculate_score(dealer_cards)
                while dealer_score < 17:
                    dealer_cards.append(random.randint(1, 13))
                    dealer_score = self._calculate_score(dealer_cards)
                
                print(f"\n🤖 Dealer hand: {dealer_cards} (Score: {dealer_score})")
                
                if dealer_score > 21:
                    print("🎉 Dealer bust! You win!")
                    self.wins += 1
                    winnings = bet * 2
                    self.total_winnings += winnings
                    if user_profile:
                        user_profile.coins += winnings
                        user_profile.add_exp(50)
                elif player_score > dealer_score:
                    print("🎉 You win!")
                    self.wins += 1
                    self.total_winnings += bet
                    if user_profile:
                        user_profile.coins += bet
                        user_profile.add_exp(50)
                else:
                    print("😞 Dealer wins!")
                    self.losses += 1
                    if user_profile:
                        user_profile.coins -= bet
            
            play_again = input("\nPlay again? (yes/no): ").strip().lower()
            if play_again != 'yes':
                break
        
        return self.get_stats()
    
    def _deal_hand(self):
        return [random.randint(1, 13) for _ in range(2)]
    
    def _calculate_score(self, cards):
        score = sum(1 if c == 1 else 10 if c > 10 else c for c in cards)
        aces = cards.count(1)
        while score > 21 and aces > 0:
            score -= 10
            aces -= 1
        return score
    
    def get_stats(self):
        win_rate = (self.wins / (self.wins + self.losses) * 100) if (self.wins + self.losses) > 0 else 0
        return {
            'game': self.name,
            'wins': self.wins,
            'losses': self.losses,
            'win_rate': round(win_rate, 1),
            'total_winnings': self.total_winnings
        }
    
    def get_info(self):
        return {
            'name': self.name,
            'description': self.description,
            'code': 'bj',
            'can_bet': True,
            'min_bet': 10,
            'max_bet': 500
        }


class SlotMachinePlugin(GamePlugin):
    """Slot Machine - Fast-paced luck-based game"""
    
    def __init__(self):
        super().__init__()
        self.name = "Slot Machine"
        self.description = "Spin the reels and hit the jackpot!"
        self.total_spins = 0
        self.wins = 0
        self.total_winnings = 0
        self.achievements = [
            Achievement('slots_jackpot', 'Triple Seven', 'Hit three sevens!', '7️⃣', {'jackpot': True}),
            Achievement('slots_lucky', 'Lucky Spinner', 'Win 20 spins', '🍀', {'wins': 20}),
            Achievement('slots_millionaire', 'High Roller', 'Win 5000+ coins in one spin', '💎', {'big_win': 5000}),
        ]
    
    def play(self, user_profile: UserProfile = None, bet_amount: int = 0):
        symbols = ['🍎', '🍌', '🍒', '7️⃣', '🎁', '⭐', '🔔', '👑']
        
        while True:
            print("\n" + "="*40)
            print("🎰 SLOT MACHINE 🎰")
            print("="*40)
            
            bet = int(input(f"💰 Spin cost (1-{user_profile.coins if user_profile else 100}): ") or "10")
            
            if user_profile and bet > user_profile.coins:
                print("❌ Insufficient coins!")
                continue
            
            if user_profile:
                user_profile.coins -= bet
            
            # Spin
            reel1 = random.choice(symbols)
            reel2 = random.choice(symbols)
            reel3 = random.choice(symbols)
            
            print(f"\n🎯 Spinning... {reel1} {reel2} {reel3}")
            
            self.total_spins += 1
            
            # Check wins
            winnings = 0
            if reel1 == reel2 == reel3:
                if reel1 == '7️⃣':
                    winnings = bet * 100
                    print("🤯 TRIPLE SEVEN! JACKPOT!!!")
                else:
                    winnings = bet * 20
                    print(f"🎉 Triple match! +{winnings} coins!")
                self.wins += 1
            elif reel1 == reel2 or reel2 == reel3 or reel1 == reel3:
                winnings = bet * 3
                print(f"✨ Double match! +{winnings} coins!")
                self.wins += 1
            else:
                print("😞 No match. Better luck next time!")
            
            self.total_winnings += winnings
            if user_profile:
                user_profile.coins += winnings
                user_profile.add_exp(25)
            
            play_again = input("\nSpin again? (yes/no): ").strip().lower()
            if play_again != 'yes':
                break
        
        return self.get_stats()
    
    def get_stats(self):
        win_rate = (self.wins / self.total_spins * 100) if self.total_spins > 0 else 0
        return {
            'game': self.name,
            'total_spins': self.total_spins,
            'wins': self.wins,
            'win_rate': round(win_rate, 1),
            'total_winnings': self.total_winnings
        }
    
    def get_info(self):
        return {
            'name': self.name,
            'description': self.description,
            'code': 'slots',
            'can_bet': True,
            'min_bet': 1,
            'max_bet': 500
        }


class TriviaPlugin(GamePlugin):
    """Trivia Challenge - Answer questions and earn rewards"""
    
    def __init__(self):
        super().__init__()
        self.name = "Trivia Challenge"
        self.description = "Test your knowledge across multiple categories!"
        self.correct = 0
        self.wrong = 0
        self.total_earnings = 0
        self.achievements = [
            Achievement('trivia_genius', 'Trivia Genius', 'Get 10 correct in a row', '🧠', {'streak': 10}),
            Achievement('trivia_master', 'Knowledge Master', 'Get 50 correct answers', '📚', {'correct': 50}),
            Achievement('trivia_speed', 'Quick Answer', 'Answer question in under 5 seconds', '⚡', {'speed': True}),
        ]
        self.questions = [
            {'q': 'What is the capital of France?', 'a': 'paris', 'cat': 'Geography'},
            {'q': 'What is 2 + 2?', 'a': '4', 'cat': 'Math'},
            {'q': 'Who wrote Romeo and Juliet?', 'a': 'shakespeare', 'cat': 'Literature'},
            {'q': 'What is the largest planet?', 'a': 'jupiter', 'cat': 'Science'},
            {'q': 'In what year did World War II end?', 'a': '1945', 'cat': 'History'},
        ]
    
    def play(self, user_profile: UserProfile = None, bet_amount: int = 0):
        num_questions = int(input("How many questions? (1-5): ") or "3")
        
        for i in range(min(num_questions, len(self.questions))):
            q_data = self.questions[i]
            print(f"\n[Question {i+1}] {q_data['q']}")
            
            answer = input("Your answer: ").strip().lower()
            
            if answer == q_data['a']:
                print("✅ Correct!")
                self.correct += 1
                if user_profile:
                    user_profile.add_exp(30)
            else:
                print(f"❌ Wrong! Answer: {q_data['a']}")
                self.wrong += 1
        
        accuracy = (self.correct / (self.correct + self.wrong) * 100) if (self.correct + self.wrong) > 0 else 0
        
        if user_profile:
            reward = self.calculate_reward(int(accuracy / 10 * 25), 'medium')
            user_profile.coins += reward
            self.total_earnings += reward
            print(f"\n🎉 +{reward} coins!")
        
        return self.get_stats()
    
    def get_stats(self):
        total = self.correct + self.wrong
        percentage = (self.correct / total * 100) if total > 0 else 0
        return {
            'game': self.name,
            'correct': self.correct,
            'wrong': self.wrong,
            'accuracy': round(percentage, 1),
            'total_earnings': self.total_earnings
        }
    
    def get_info(self):
        return {
            'name': self.name,
            'description': self.description,
            'code': 'trivia',
            'competitive': True
        }


class DiceRollerPlugin(GamePlugin):
    """Dice Roller - Roll and bet on outcomes"""
    
    def __init__(self):
        super().__init__()
        self.name = "Dice Roller"
        self.description = "Roll the dice and predict the outcome!"
        self.wins = 0
        self.losses = 0
        self.total_winnings = 0
        self.achievements = [
            Achievement('dice_lucky', 'Lucky Roller', 'Win 10 times', '🎲', {'wins': 10}),
            Achievement('dice_streaker', 'Hot Hands', 'Win 5 in a row', '🔥', {'streak': 5}),
            Achievement('dice_snake_eyes', 'Snake Eyes', 'Roll two ones', '👀', {'snake_eyes': True}),
        ]
    
    def play(self, user_profile: UserProfile = None, bet_amount: int = 0):
        while True:
            print("\n" + "="*40)
            print("🎲 DICE ROLLER 🎲")
            print("="*40)
            
            bet = int(input(f"💰 Enter bet (1-{user_profile.coins if user_profile else 100}): ") or "10")
            
            if user_profile and bet > user_profile.coins:
                print("❌ Insufficient coins!")
                continue
            
            prediction = input("Predict: Higher (h), Lower (l), or Exact (e) for next roll? ").strip().lower()
            
            if prediction not in ['h', 'l', 'e']:
                print("❌ Invalid prediction!")
                continue
            
            if user_profile:
                user_profile.coins -= bet
            
            # Roll two dice
            die1 = random.randint(1, 6)
            die2 = random.randint(1, 6)
            total = die1 + die2
            
            print(f"\n🎲 Rolling... {die1} + {die2} = {total}")
            
            winnings = 0
            if prediction == 'h' and total > 7:
                winnings = bet * 2
                print(f"🎉 You win! +{winnings} coins!")
                self.wins += 1
            elif prediction == 'l' and total < 7:
                winnings = bet * 2
                print(f"🎉 You win! +{winnings} coins!")
                self.wins += 1
            elif prediction == 'e' and total == 7:
                winnings = bet * 5
                print(f"🤯 Exact! +{winnings} coins!")
                self.wins += 1
            else:
                print("😞 Wrong prediction!")
                self.losses += 1
            
            self.total_winnings += winnings
            if user_profile:
                user_profile.coins += winnings
                user_profile.add_exp(20)
            
            play_again = input("\nRoll again? (yes/no): ").strip().lower()
            if play_again != 'yes':
                break
        
        return self.get_stats()
    
    def get_stats(self):
        win_rate = (self.wins / (self.wins + self.losses) * 100) if (self.wins + self.losses) > 0 else 0
        return {
            'game': self.name,
            'wins': self.wins,
            'losses': self.losses,
            'win_rate': round(win_rate, 1),
            'total_winnings': self.total_winnings
        }
    
    def get_info(self):
        return {
            'name': self.name,
            'description': self.description,
            'code': 'dice',
            'can_bet': True,
            'min_bet': 10,
            'max_bet': 500
        }


# ============================================
# PREMIUM GAME MANAGER & TOURNAMENT ENGINE
# ============================================

class Tournament:
    """Tournament system for competitive gaming"""
    def __init__(self, tournament_id: str, game_code: str, entry_fee: int, prize_pool: int):
        self.tournament_id = tournament_id
        self.game_code = game_code
        self.entry_fee = entry_fee
        self.prize_pool = prize_pool
        self.participants = []
        self.leaderboard = []
        self.status = 'open'  # open, in_progress, completed
        self.created_at = datetime.now().isoformat()
    
    def register_player(self, user_profile: UserProfile) -> bool:
        """Register a player for tournament"""
        if user_profile.coins >= self.entry_fee:
            self.participants.append(user_profile.user_id)
            user_profile.coins -= self.entry_fee
            return True
        return False
    
    def finalize_leaderboard(self):
        """Finalize tournament and distribute prizes"""
        self.status = 'completed'
        # Prize distribution: 50% first, 30% second, 20% third
        prizes = [
            int(self.prize_pool * 0.5),
            int(self.prize_pool * 0.3),
            int(self.prize_pool * 0.2)
        ]
        return prizes

class Leaderboard:
    """Global leaderboard system"""
    def __init__(self):
        self.entries = {}  # {user_id: {score, rank, timestamp}}
    
    def update_score(self, user_id: str, game: str, score: int, user_profile: UserProfile):
        """Update leaderboard entry"""
        key = f"{game}_{user_id}"
        self.entries[key] = {
            'user_id': user_id,
            'username': user_profile.username,
            'game': game,
            'score': score,
            'level': user_profile.level,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_top(self, game: str, limit: int = 10) -> List[Dict]:
        """Get top players for a game"""
        game_entries = [e for e in self.entries.values() if e['game'] == game]
        sorted_entries = sorted(game_entries, key=lambda x: x['score'], reverse=True)
        return sorted_entries[:limit]

class GameManager:
    """Enhanced game manager with premium features"""
    
    def __init__(self):
        self.plugins = {
            'rps': RockPaperScissorsPlugin(),
            'gtn': GuessTheNumberPlugin(),
            'mq': MathQuizPlugin(),
            'bj': BlackjackPlugin(),
            'slots': SlotMachinePlugin(),
            'trivia': TriviaPlugin(),
            'dice': DiceRollerPlugin()
        }
        self.users_file = 'users_profiles.json'
        self.user_profiles = self.load_users()
        self.leaderboard = Leaderboard()
        self.tournaments = {}
        self.current_user = None
        self.session_stats = []
        
        # Initialize leaderboards from file
        self.load_leaderboard()
    
    def save_users(self):
        """Save all user profiles"""
        data = {
            user_id: profile.to_dict()
            for user_id, profile in self.user_profiles.items()
        }
        with open(self.users_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load_users(self) -> Dict[str, UserProfile]:
        """Load user profiles"""
        if os.path.exists(self.users_file):
            try:
                with open(self.users_file, 'r') as f:
                    data = json.load(f)
                    return {
                        user_id: UserProfile(user_id, p.get('username'))
                        for user_id, p in data.items()
                    }
            except:
                pass
        return {}
    
    def load_leaderboard(self):
        """Load leaderboard from stats"""
        stats_file = 'user_stats.json'
        if os.path.exists(stats_file):
            try:
                with open(stats_file, 'r') as f:
                    stats = json.load(f)
                    for stat in stats:
                        # Reconstruct leaderboard
                        pass
            except:
                pass
    
    def register_user(self, username: str) -> UserProfile:
        """Register new user"""
        user_id = str(uuid.uuid4())[:12]
        profile = UserProfile(user_id, username)
        self.user_profiles[user_id] = profile
        self.current_user = profile
        self.save_users()
        print(f"\n✅ Welcome {username}! Your account ID: {user_id}")
        return profile
    
    def login_user(self, user_id: str) -> Optional[UserProfile]:
        """Login existing user"""
        if user_id in self.user_profiles:
            self.current_user = self.user_profiles[user_id]
            self.current_user.last_login = datetime.now().isoformat()
            self.save_users()
            return self.current_user
        return None
    
    def display_premium_shop(self):
        """Display premium cosmetics and boosters shop"""
        print("\n" + "="*50)
        print("💎 PREMIUM SHOP 💎")
        print("="*50)
        print("\n🎁 Cosmetics & Boosters:")
        print("  [1] 100 Premium Coins - $4.99")
        print("  [2] 500 Premium Coins - $19.99 (20% off)")
        print("  [3] 2x XP Booster (7 days) - $2.99")
        print("  [4] VIP Badge - $9.99/month")
        print("  [5] Back")
        print("="*50)
    
    def display_achievements(self):
        """Display player achievements"""
        if not self.current_user:
            print("❌ Please login first")
            return
        
        print("\n" + "="*50)
        print(f"🏆 ACHIEVEMENTS - {self.current_user.username} 🏆")
        print("="*50)
        
        all_achievements = []
        for plugin in self.plugins.values():
            all_achievements.extend(plugin.achievements)
        
        for achievement in all_achievements:
            status = "✅" if achievement.id in self.current_user.achievements else "🔒"
            print(f"\n{achievement.icon} {achievement.name} {status}")
            print(f"   {achievement.description}")
    
    def display_leaderboard(self, game_code: str = None):
        """Display global leaderboard"""
        print("\n" + "="*50)
        print("🏆 GLOBAL LEADERBOARD 🏆")
        print("="*50)
        
        if game_code:
            top_players = self.leaderboard.get_top(game_code, 10)
            print(f"\nTop 10 - {game_code.upper()}:")
            for i, entry in enumerate(top_players, 1):
                print(f"{i}. {entry['username']} - Level {entry['level']} - Score: {entry['score']}")
        else:
            print("\nSelect a game to view leaderboard")
        
        print("="*50)
    
    def display_user_profile(self):
        """Display detailed user profile"""
        if not self.current_user:
            print("❌ Please login first")
            return
        
        user = self.current_user
        print("\n" + "="*60)
        print(f"👤 PROFILE - {user.username}")
        print("="*60)
        print(f"Level: {user.level} | XP: {user.exp}")
        print(f"💰 Coins: {user.coins} | 💎 Premium Coins: {user.premium_coins}")
        print(f"⏳ Total Playtime: {user.total_playtime//3600}h {(user.total_playtime%3600)//60}m")
        print(f"🔥 Current Streak: {user.streaks['current']} | Best Streak: {user.streaks['best']}")
        
        if user.premium_member:
            print(f"👑 Premium Member until {user.premium_expiry}")
        
        print(f"\n🏆 Achievements: {len(user.achievements)} unlocked")
        print(f"📅 Member since: {user.created_at[:10]}")
        print(f"Last login: {user.last_login[:10]}")
        print("="*60)
    
    def display_menu(self):
        """Display enhanced main menu"""
        if not self.current_user:
            print("\n" + "="*50)
            print("🎮 GAMEBOT PREMIUM 🎮")
            print("="*50)
            print("\n[1] Register New Account")
            print("[2] Login")
            print("[3] Play as Guest")
            print("[4] Exit")
            return
        
        user = self.current_user
        print("\n" + "="*60)
        print(f"🎮 GAMEBOT PREMIUM - {user.username}")
        print(f"Level {user.level} | 💰 {user.coins} coins | 💎 {user.premium_coins} premium")
        print("="*60)
        print("\n🎮 Games:")
        for code, plugin in self.plugins.items():
            info = plugin.get_info()
            print(f"  [{code}] {info['name']}")
        print("\n📊 Account:")
        print(f"  [profile] View Profile")
        print(f"  [achievements] View Achievements")
        print(f"  [leaderboard] View Leaderboards")
        print(f"  [shop] Premium Shop")
        print(f"  [daily] Claim Daily Reward")
        print(f"  [logout] Logout")
        print(f"  [quit] Exit")
        print("="*60)
    
    def run(self):
        """Main game loop with authentication"""
        print("\n" + "="*60)
        print("🎮 GAMEBOT PREMIUM - Next Generation Gaming Platform 🎮")
        print("="*60)
        
        while True:
            if not self.current_user:
                # Authentication menu
                self.display_menu()
                choice = input("\nEnter your choice: ").strip().lower()
                
                if choice == '1':
                    username = input("Enter username: ").strip()
                    self.register_user(username)
                elif choice == '2':
                    user_id = input("Enter your account ID: ").strip()
                    profile = self.login_user(user_id)
                    if profile:
                        print(f"✅ Welcome back, {profile.username}!")
                    else:
                        print("❌ Invalid account ID")
                elif choice == '3':
                    self.current_user = UserProfile("guest_" + str(uuid.uuid4())[:8])
                    print(f"👤 Playing as guest")
                elif choice == '4':
                    print("👋 Goodbye!")
                    break
            else:
                # Main game menu
                self.display_menu()
                choice = input("\nEnter your choice: ").strip().lower()
                
                if choice in self.plugins:
                    print(f"\n🎮 Starting {self.plugins[choice].name}...")
                    stats = self.plugins[choice].play(self.current_user)
                    self.session_stats.append(stats)
                    self.save_users()
                
                elif choice == 'profile':
                    self.display_user_profile()
                
                elif choice == 'achievements':
                    self.display_achievements()
                
                elif choice == 'leaderboard':
                    game = input("Enter game code (rps/gtn/mq): ").strip()
                    self.display_leaderboard(game)
                
                elif choice == 'shop':
                    self.display_premium_shop()
                
                elif choice == 'daily':
                    reward = self.current_user.claim_daily_reward()
                    if reward > 0:
                        print(f"🎉 Daily reward claimed! +{reward} coins")
                    else:
                        print("⏰ Come back tomorrow for your next reward!")
                    self.save_users()
                
                elif choice == 'logout':
                    print(f"👋 Goodbye, {self.current_user.username}!")
                    self.current_user = None
                
                elif choice == 'quit':
                    print("👋 Thanks for playing! See you next time!")
                    break


# ============================================
# MAIN ENTRY POINT
# ============================================

if __name__ == "__main__":
    try:
        manager = GameManager()
        manager.run()
    except KeyboardInterrupt:
        print("\n\n⚠️  Game interrupted. Your progress has been saved!")
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
        import traceback
        traceback.print_exc()