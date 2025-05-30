import sys
import os

# Add the project root directory to Python's path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.lib.VoxaCommunications_Router.cryptography.relayintegrity import RelayIntegrityManager

if __name__ == "__main__":
    # Initialize the RelayIntegrityManager
    relay_integrity_manager = RelayIntegrityManager()

    # Print the directories to verify they are set up correctly
    print("Key Directory:", relay_integrity_manager.directories["key_dir"])
    print("Fernet Directory:", relay_integrity_manager.directories["fernet_dir"])
    print("Asymmetric Directory:", relay_integrity_manager.directories["asymmetric_dir"])