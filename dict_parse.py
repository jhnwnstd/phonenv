from typing import Set, Optional
from pathlib import Path


class DictionaryProcessor:
    """Processes and manages word dictionaries."""
    
    def __init__(self, input_file: str = "data/input.txt", encoding: str = "utf-8"):
        """Initialize the dictionary processor.

        Args:
            input_file: Path to the input dictionary file
            encoding: File encoding (default: utf-8)
        """
        self.input_file = Path(input_file)
        self.encoding = encoding
    
    def load_words(self) -> Set[str]:
        """Load words from the input file.
        
        Returns:
            Set of words from the file
            
        Raises:
            FileNotFoundError: If input file doesn't exist
            IOError: If file cannot be read
        """
        if not self.input_file.exists():
            return set()
            
        try:
            with self.input_file.open('r', encoding=self.encoding) as f:
                return {line.strip() for line in f if line.strip()}
        except (IOError, OSError) as e:
            raise IOError(f"Cannot read file {self.input_file}: {e}") from e
    
    def save_words(self, words: Set[str]) -> None:
        """Save words to the input file.
        
        Args:
            words: Set of words to save
            
        Raises:
            IOError: If file cannot be written
        """
        try:
            # Ensure directory exists
            self.input_file.parent.mkdir(parents=True, exist_ok=True)
            
            with self.input_file.open('w', encoding='utf-8') as f:
                for word in sorted(words):
                    f.write(f"{word}\n")
        except (IOError, OSError) as e:
            raise IOError(f"Cannot write to file {self.input_file}: {e}") from e
    
    def add_word(self, word: str) -> bool:
        """Add a word to the dictionary.
        
        Args:
            word: Word to add
            
        Returns:
            True if word was added, False if it already existed
        """
        words = self.load_words()
        if word in words:
            return False
        
        words.add(word)
        self.save_words(words)
        return True
    
    def remove_words_containing(self, substring: str) -> int:
        """Remove words containing a specific substring.
        
        Args:
            substring: Substring to filter out
            
        Returns:
            Number of words removed
        """
        words = self.load_words()
        original_count = len(words)
        
        filtered_words = {word for word in words if substring not in word}
        
        self.save_words(filtered_words)
        return original_count - len(filtered_words)
    
    def clear_dictionary(self) -> None:
        """Clear all words from the dictionary."""
        self.save_words(set())
    
    def print_dictionary(self) -> None:
        """Print all words in the dictionary to console."""
        words = self.load_words()
        if not words:
            print("Dictionary is empty")
            return
            
        print(f"Dictionary contains {len(words)} words:")
        for word in sorted(words):
            print(word)
    
    def get_stats(self) -> dict:
        """Get statistics about the dictionary.
        
        Returns:
            Dictionary with statistics
        """
        words = self.load_words()
        return {
            'total_words': len(words),
            'unique_letters': len(set(''.join(words).lower())),
            'avg_word_length': sum(len(word) for word in words) / len(words) if words else 0,
            'longest_word': max(words, key=len) if words else None,
            'shortest_word': min(words, key=len) if words else None
        }
    
    def process_dictionary(
        self, 
        append: Optional[str] = None,
        print_dict: bool = False,
        delete_substring: Optional[str] = None,
        clear_file: bool = False
    ) -> None:
        """Process dictionary with various operations.
        
        Args:
            append: Word to append to dictionary
            print_dict: Whether to print dictionary to console
            delete_substring: Substring to delete words containing it
            clear_file: Whether to clear the file first
        """
        print(f"Processing dictionary from '{self.input_file}'")
        
        try:
            # Clear file if requested
            if clear_file:
                self.clear_dictionary()
                words = set()
            else:
                words = self.load_words()
            
            # Add word if provided
            if append:
                if append in words:
                    print(f"Word '{append}' already exists in dictionary")
                else:
                    words.add(append)
                    print(f"Added '{append}' to dictionary")
            
            # Remove words containing substring
            if delete_substring:
                original_count = len(words)
                words = {word for word in words if delete_substring not in word}
                removed_count = original_count - len(words)
                print(f"Removed {removed_count} words containing '{delete_substring}'")
            
            # Save changes
            self.save_words(words)
            
            # Print dictionary if requested
            if print_dict:
                self.print_dictionary()
            else:
                stats = self.get_stats()
                print(f"Dictionary now contains {stats['total_words']} words")
                
        except IOError as e:
            print(f"Error processing dictionary: {e}")


# Backward compatibility function
def process_dictionary(
    input_file: str,
    append: Optional[str] = None,
    print_dict: bool = False,
    delete_substring: Optional[str] = None,
    clear_file: bool = False
) -> None:
    """Legacy function for backward compatibility."""
    processor = DictionaryProcessor(input_file)
    processor.process_dictionary(append, print_dict, delete_substring, clear_file)