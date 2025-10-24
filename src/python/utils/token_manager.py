#!/usr/bin/env python3
"""
GitHub Token Manager - Automate token creation and configuration
Automatically creates GitHub Personal Access Tokens and configures the scraper
"""

import json
import os
import sys
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import random
import string
from datetime import datetime, timedelta

class GitHubTokenManager:
    def __init__(self):
        self.config_path = "configs/config.json"
        self.tokens = []
        self.driver = None
        
    def setup_driver(self):
        """Setup Chrome driver with appropriate options"""
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Keep browser open for user interaction
        chrome_options.add_experimental_option("detach", True)
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
    def generate_token_name(self, index):
        """Generate a unique token name"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
        return f"scraper_token_{index}_{timestamp}_{random_suffix}"
    
    def verify_login_retry(self):
        """Retry login verification after user confirms they've logged in"""
        try:
            self.driver.refresh()
            time.sleep(2)
            
            # Check for user-specific elements again
            login_indicators = [
                "//button[@aria-label='View profile and more']",
                "//img[@alt='@']",
                "//summary[contains(@aria-label, 'View profile')]",
                "//a[contains(@href, '/settings')]",
                "//div[contains(@class, 'AppHeader-user')]"
            ]
            
            for selector in login_indicators:
                try:
                    element = WebDriverWait(self.driver, 3).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    if element:
                        print("✅ Login verified after retry!")
                        return True
                except:
                    continue
            
            print("⚠️  Still cannot verify login. Proceeding anyway...")
            return True
            
        except Exception as e:
            print(f"⚠️  Retry verification failed: {e}")
            return True
    
    def verify_login_and_access(self):
        """Verify login and access to tokens page"""
        try:
            print("🔗 Navigating to Personal Access Tokens page...")
            self.driver.get("https://github.com/settings/tokens")
            time.sleep(3)
            
            # Check if we're actually on the tokens page
            tokens_page_indicators = [
                "//h1[contains(text(), 'Personal access tokens')]",
                "//h2[contains(text(), 'Personal access tokens')]",
                "//a[contains(@href, '/settings/tokens/new')]",
                "//button[contains(text(), 'Generate new token')]",
                "//a[contains(text(), 'Generate new token')]",
                "//div[contains(@class, 'settings-tokens')]",
                "//*[contains(text(), 'Fine-grained personal access tokens')]",
                "//*[contains(text(), 'Tokens (classic)')]"
            ]
            
            for selector in tokens_page_indicators:
                try:
                    element = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    if element:
                        print("✅ Successfully accessed Personal Access Tokens page!")
                        return True
                except:
                    continue
            
            print("❌ Could not find tokens page elements. May not be logged in or page changed.")
            return False
            
        except Exception as e:
            print(f"❌ Error accessing tokens page: {e}")
            return False
    
    def create_tokens_interactive(self, num_tokens):
        """Create tokens with user guidance through browser automation"""
        print(f"🚀 Starting automated token creation for {num_tokens} tokens...")
        print("\n📋 INSTRUCTIONS:")
        print("1. A Chrome browser will open to GitHub login")
        print("2. Please log in to your GitHub account manually")
        print("3. The script will guide you through token creation")
        print("4. DO NOT close the browser - the script controls it")
        print("\nPress Enter when ready to start...")
        input()
        
        self.setup_driver()
        
        try:
            # Navigate to GitHub login
            print("🌐 Opening GitHub...")
            self.driver.get("https://github.com/login")
            
            print("\n⏳ Please log in to GitHub manually in the browser window...")
            print("Click in this terminal and press Enter AFTER you've logged in successfully")
            input()
            
            # Verify login by checking for user-specific elements
            print("🔍 Verifying login...")
            try:
                # First try to access the main page to check if logged in
                self.driver.get("https://github.com")
                time.sleep(2)
                
                # Look for user-specific elements that indicate login
                login_indicators = [
                    "//button[@aria-label='View profile and more']",  # User menu button
                    "//img[@alt='@']",  # Profile avatar
                    "//summary[contains(@aria-label, 'View profile')]",  # Profile dropdown
                    "//a[@data-analytics-event='Header, go to dashboard, icon:logo']",  # Dashboard link
                    "//a[contains(@href, '/settings')]",  # Settings link
                    "//button[contains(@class, 'Header-link') and contains(@aria-label, 'Create new')]",  # Create new button
                    "//*[@data-target='notification-indicator.link']",  # Notification bell
                    "//a[contains(@href, '/notifications')]",  # Notifications link
                    "//div[contains(@class, 'AppHeader-user')]",  # User header section
                    "//button[contains(@class, 'AppHeader-user')]",  # User button
                ]
                
                logged_in = False
                for selector in login_indicators:
                    try:
                        element = WebDriverWait(self.driver, 3).until(
                            EC.presence_of_element_located((By.XPATH, selector))
                        )
                        if element:
                            logged_in = True
                            print("✅ Login verified! User-specific elements found.")
                            break
                    except:
                        continue
                
                if not logged_in:
                    # Check if we're on a login page or see login button
                    try:
                        login_elements = [
                            "//a[contains(text(), 'Sign in')]",
                            "//a[contains(@href, '/login')]",
                            "//input[@name='login']",
                            "//input[@name='password']"
                        ]
                        
                        for selector in login_elements:
                            try:
                                element = self.driver.find_element(By.XPATH, selector)
                                if element:
                                    print("❌ Not logged in - login elements detected.")
                                    print("💡 Please log in to GitHub first, then press Enter to continue.")
                                    input("Press Enter after logging in...")
                                    # Re-check after user confirms login
                                    return self.verify_login_retry()
                            except:
                                continue
                                
                    except:
                        pass
                    
                    print("⚠️  Could not verify login status with certainty.")
                    print("💡 If you're logged in, the script will continue. If not, it will fail safely.")
                    proceed = input("Continue anyway? (y/N): ").lower().strip()
                    if proceed != 'y':
                        print("❌ Aborted by user.")
                        return False
                
                return True
                    
            except Exception as e:
                print(f"⚠️  Login verification error: {e}")
                print("💡 Continuing anyway - the script will fail safely if not logged in.")
                proceed = input("Continue? (y/N): ").lower().strip()
                return proceed == 'y'
            
            # Verify we can access the tokens page before starting
            verification_success = self.verify_login_and_access()
            if not verification_success:
                print("❌ Cannot access GitHub tokens page. Please ensure you're logged in.")
                return False
            
            # Create tokens one by one
            for i in range(num_tokens):
                print(f"\n🔑 Creating token {i+1}/{num_tokens}...")
                token = self.create_single_token(i+1)
                if token:
                    self.tokens.append(token)
                    print(f"✅ Token {i+1} created successfully!")
                    print(f"   Token preview: {token[:8]}...")
                    
                    # Small delay between token creations
                    if i < num_tokens - 1:
                        print("⏱️  Waiting 3 seconds before next token...")
                        time.sleep(3)
                else:
                    print(f"❌ Failed to create token {i+1}")
                    break
            
            if len(self.tokens) == num_tokens:
                print(f"\n🎉 Successfully created all {num_tokens} tokens!")
                self.update_config()
                self.test_tokens()
                return True
            else:
                print(f"\n⚠️  Created {len(self.tokens)}/{num_tokens} tokens")
                if self.tokens:
                    self.update_config()
                return False
                
        except Exception as e:
            print(f"❌ Error during token creation: {e}")
            return False
        finally:
            print("\n🔚 Keeping browser open for verification...")
            print("You can close the browser manually when done.")
    
    def create_single_token(self, token_num):
        """Create a single GitHub token"""
        try:
            # Navigate to token creation page
            self.driver.get("https://github.com/settings/tokens/new")
            
            # Wait for page to load - try multiple selectors for the description field
            description_selectors = [
                (By.NAME, "oauth_access[description]"),
                (By.ID, "oauth_access_description"),
                (By.CSS_SELECTOR, "input[name*='description']"),
                (By.CSS_SELECTOR, "input[placeholder*='name']"),
                (By.CSS_SELECTOR, "input[placeholder*='What']"),
                (By.XPATH, "//input[contains(@placeholder, 'What')]"),
                (By.XPATH, "//input[contains(@name, 'description')]"),
                (By.XPATH, "//label[contains(text(), 'Note')]/following-sibling::input"),
                (By.XPATH, "//label[contains(text(), 'Note')]/..//input")
            ]
            
            description_field = None
            for selector_type, selector_value in description_selectors:
                try:
                    description_field = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((selector_type, selector_value))
                    )
                    if description_field:
                        break
                except:
                    continue
            
            if not description_field:
                print("❌ Could not find token description field")
                return None
            
            # Fill in token name
            token_name = self.generate_token_name(token_num)
            description_field.clear()
            description_field.send_keys(token_name)
            print(f"   Token name: {token_name}")
            
            # Set expiration to 1 year
            try:
                expiration_select = self.driver.find_element(By.NAME, "oauth_access[expires_at]")
                self.driver.execute_script("arguments[0].value = arguments[1];", 
                    expiration_select, (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d"))
            except:
                print("⚠️  Could not set expiration date automatically")
            
            # Select required scopes
            scopes = [
                "repo",           # Full repository access
                "read:user",      # Read user profile data
                "user:email",     # Read email addresses
                "read:org"        # Read organization data
            ]
            
            for scope in scopes:
                try:
                    checkbox = self.driver.find_element(By.ID, f"oauth_access_scope_{scope}")
                    if not checkbox.is_selected():
                        self.driver.execute_script("arguments[0].click();", checkbox)
                except:
                    print(f"⚠️  Could not find scope: {scope}")
            
            # Generate token
            generate_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            generate_button.click()
            
            # Wait for token to be generated and displayed - try multiple selectors
            token_selectors = [
                "input[data-target='token-input.token']",
                "input[readonly][value^='ghp_']",
                "input[readonly][value^='github_pat_']",
                "input[class*='token']",
                "input[id*='token']",
                "code",
                "pre",
                "span[class*='token']"
            ]
            
            token = None
            for selector in token_selectors:
                try:
                    token_element = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    if token_element:
                        token_value = token_element.get_attribute("value") or token_element.text
                        if token_value and (token_value.startswith(("ghp_", "github_pat_"))):
                            token = token_value.strip()
                            break
                except:
                    continue
            
            if not token:
                # Try XPath selectors as backup
                xpath_selectors = [
                    "//input[contains(@value, 'ghp_')]",
                    "//input[contains(@value, 'github_pat_')]",
                    "//*[contains(text(), 'ghp_')]",
                    "//*[contains(text(), 'github_pat_')]"
                ]
                
                for selector in xpath_selectors:
                    try:
                        token_element = self.driver.find_element(By.XPATH, selector)
                        if token_element:
                            token_value = token_element.get_attribute("value") or token_element.text
                            if token_value and (token_value.startswith(("ghp_", "github_pat_"))):
                                token = token_value.strip()
                                break
                    except:
                        continue
            
            if token and token.startswith(("ghp_", "github_pat_")):
                return token
            else:
                print("❌ Failed to extract valid token")
                print("   Please check if the token was created successfully in the browser")
                return None
                
        except Exception as e:
            print(f"❌ Error creating token: {e}")
            return None
    
    def update_config(self):
        """Update the scraper configuration with new tokens"""
        try:
            # Load existing config
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
            else:
                config = self.get_default_config()
            
            # Update tokens
            config["github_tokens"] = self.tokens
            
            # Save updated config
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            print(f"✅ Configuration updated with {len(self.tokens)} tokens")
            print(f"   Config file: {self.config_path}")
            
            # Also set environment variable
            os.environ["GITHUB_TOKENS"] = ",".join(self.tokens)
            
            # Create .env file for persistence
            with open(".env", "w") as f:
                f.write(f"GITHUB_TOKENS={','.join(self.tokens)}\n")
            
            print("✅ Environment variable GITHUB_TOKENS set")
            print("✅ .env file created for persistence")
            
        except Exception as e:
            print(f"❌ Error updating configuration: {e}")
    
    def get_default_config(self):
        """Get default configuration structure"""
        return {
            "github_tokens": [],
            "storage": {
                "primary_path": "\\\\192.168.1.66\\plex3\\codelupe\\repos",
                "backup_path": "//192.168.1.66/plex3/codebase/repos",
                "max_primary_gb": 14000,
                "max_backup_gb": 10000
            },
            "performance": {
                "workers_per_token": 4,
                "repos_per_hour_per_token": 5000,
                "max_requests_per_second": 2,
                "concurrent_clones": 8
            },
            "quality_filters": {
                "min_stars": 10,
                "min_quality_score": 30,
                "clone_quality_threshold": 70,
                "max_repo_size_kb": 100000,
                "min_recent_days": 365
            },
            "target_languages": [
                "Python", "Go", "Dart", "TypeScript", "JavaScript", "C#", "Rust", "SQL"
            ],
            "target_technologies": [
                "angular", "react", "vue", "flutter", "postgresql", "elasticsearch",
                "mongodb", "machine-learning", "artificial-intelligence", "tensorflow",
                "pytorch", "fastapi", "django", "gin", "fiber", "microservices",
                "kubernetes", "docker"
            ]
        }
    
    def test_tokens(self):
        """Test all tokens to ensure they work"""
        print(f"\n🧪 Testing {len(self.tokens)} tokens...")
        
        working_tokens = []
        failed_tokens = []
        
        for i, token in enumerate(self.tokens):
            print(f"   Testing token {i+1}: {token[:8]}...", end=" ")
            
            try:
                headers = {
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "GitHubTokenManager/1.0"
                }
                
                response = requests.get("https://api.github.com/user", headers=headers, timeout=10)
                
                if response.status_code == 200:
                    user_data = response.json()
                    username = user_data.get("login", "unknown")
                    rate_limit = response.headers.get("X-RateLimit-Limit", "unknown")
                    print(f"✅ OK (User: {username}, Rate Limit: {rate_limit})")
                    working_tokens.append(token)
                else:
                    print(f"❌ FAILED (Status: {response.status_code})")
                    failed_tokens.append(token)
                    
            except Exception as e:
                print(f"❌ ERROR ({str(e)[:30]}...)")
                failed_tokens.append(token)
        
        print(f"\n📊 Token Test Results:")
        print(f"   ✅ Working: {len(working_tokens)}/{len(self.tokens)}")
        print(f"   ❌ Failed: {len(failed_tokens)}/{len(self.tokens)}")
        
        if failed_tokens:
            print(f"\n⚠️  Failed tokens (consider removing):")
            for token in failed_tokens:
                print(f"   - {token[:8]}...")
        
        # Update config with only working tokens
        if working_tokens != self.tokens:
            self.tokens = working_tokens
            self.update_config()
            print(f"✅ Configuration updated with {len(working_tokens)} working tokens")
        
        return len(working_tokens)
    
    def list_existing_tokens(self):
        """List tokens from current configuration"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    tokens = config.get("github_tokens", [])
                    
                # Filter out placeholder tokens - be more strict
                real_tokens = []
                for t in tokens:
                    # Skip obvious placeholders
                    if (t.startswith("ghp_your_token_") or 
                        "your_token" in t or 
                        "token_here" in t or
                        t.endswith("_here") or
                        len(t) < 30):  # Real GitHub tokens are much longer
                        continue
                    # Only include tokens that look like real GitHub tokens
                    if (t.startswith(("ghp_", "github_pat_")) and len(t) >= 30):
                        real_tokens.append(t)
                    
                if real_tokens:
                    print(f"📋 Found {len(real_tokens)} existing tokens:")
                    for i, token in enumerate(real_tokens):
                        print(f"   {i+1}. {token[:8]}...")
                    return real_tokens
                else:
                    print("📋 No real tokens found in configuration (only placeholders)")
                    return []
            else:
                print("📋 No configuration file found")
                return []
        except Exception as e:
            print(f"❌ Error reading configuration: {e}")
            return []

def main():
    print("🚀 GitHub Token Manager for Ultimate Scraper")
    print("=" * 50)
    
    manager = GitHubTokenManager()
    
    # Check for existing tokens
    existing_tokens = manager.list_existing_tokens()
    
    if existing_tokens:
        print(f"\nYou already have {len(existing_tokens)} tokens configured.")
        choice = input("Do you want to (A)dd more tokens, (R)eplace all tokens, or (T)est existing tokens? [A/R/T]: ").upper()
        
        if choice == "T":
            manager.tokens = existing_tokens
            working_count = manager.test_tokens()
            print(f"\n✅ Token testing complete. {working_count} working tokens configured.")
            return
        elif choice == "R":
            pass  # Continue to create new tokens
        elif choice == "A":
            additional = int(input("How many additional tokens do you want to create? "))
            if manager.create_tokens_interactive(additional):
                # Combine with existing tokens
                all_tokens = existing_tokens + manager.tokens
                manager.tokens = all_tokens
                manager.update_config()
                print(f"\n✅ Total tokens: {len(all_tokens)} ({len(existing_tokens)} existing + {len(manager.tokens)} new)")
            return
        else:
            print("Invalid choice. Exiting.")
            return
    
    # Get number of tokens to create
    try:
        num_tokens = int(input("\nHow many GitHub tokens do you need? (recommended: 6-8): "))
        if num_tokens < 1 or num_tokens > 50:
            print("❌ Please enter a reasonable number between 1 and 50")
            return
    except ValueError:
        print("❌ Please enter a valid number")
        return
    
    # Create tokens
    if manager.create_tokens_interactive(num_tokens):
        print("\n🎉 Token creation completed successfully!")
        print(f"✅ {len(manager.tokens)} tokens are ready for the scraper")
        print(f"✅ Configuration saved to: {manager.config_path}")
        print(f"✅ Environment variable GITHUB_TOKENS set")
        print("\n🚀 You can now run the scraper with:")
        print("   go run ultimate_github_scraper.go")
    else:
        print("\n❌ Token creation failed or incomplete")
        if manager.tokens:
            print(f"   {len(manager.tokens)} tokens were created successfully")

if __name__ == "__main__":
    main()