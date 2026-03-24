"""
Pine Script Validator Module
============================
Pre-flight syntax checking for Pine Script before sending to TradingView.
Catches common errors that would fail compilation.
"""

import re
from typing import List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class ErrorSeverity(Enum):
    ERROR = "error"      # Will definitely fail
    WARNING = "warning"  # Might cause issues
    INFO = "info"        # Style suggestion


@dataclass
class ValidationError:
    line_number: int
    column: int
    message: str
    severity: ErrorSeverity
    suggestion: Optional[str] = None


class PineValidator:
    """
    Validates Pine Script syntax before TradingView compilation.
    Catches common errors that the AI might produce.
    """
    
    # Reserved keywords in Pine Script v5
    RESERVED_KEYWORDS = {
        'if', 'else', 'for', 'while', 'switch', 'import', 'export',
        'var', 'varip', 'true', 'false', 'na', 'and', 'or', 'not',
        'int', 'float', 'bool', 'string', 'color', 'line', 'label',
        'box', 'table', 'array', 'matrix', 'map', 'series', 'simple',
        'const', 'input', 'strategy', 'indicator', 'library'
    }
    
    # Functions that are commonly misused
    STRATEGY_FUNCTIONS = {
        'strategy.entry', 'strategy.exit', 'strategy.close',
        'strategy.close_all', 'strategy.cancel', 'strategy.cancel_all'
    }
    
    def __init__(self):
        self.errors: List[ValidationError] = []
    
    def validate(self, script: str) -> Tuple[bool, List[ValidationError]]:
        """
        Validate a Pine Script.
        Returns (is_valid, errors).
        """
        self.errors = []
        
        lines = script.split('\n')
        
        # Run all validation checks
        self._check_version(lines)
        self._check_strategy_declaration(lines)
        self._check_multiline_calls(lines)
        self._check_continuation_lines(lines)
        self._check_string_literals(lines)
        self._check_operators(lines)
        self._check_brackets(script)
        self._check_common_mistakes(lines)
        
        # Check if any errors (not just warnings)
        has_errors = any(e.severity == ErrorSeverity.ERROR for e in self.errors)
        
        return (not has_errors, self.errors)
    
    def _check_version(self, lines: List[str]) -> None:
        """Check for version declaration."""
        has_version = False
        for i, line in enumerate(lines):
            if line.strip().startswith('//@version='):
                has_version = True
                # Check version number
                match = re.search(r'//@version=(\d+)', line)
                if match:
                    version = int(match.group(1))
                    if version < 5:
                        self.errors.append(ValidationError(
                            line_number=i + 1,
                            column=0,
                            message=f"Pine Script version {version} is outdated. Use version 5.",
                            severity=ErrorSeverity.WARNING,
                            suggestion="Change to //@version=5"
                        ))
                break
        
        if not has_version:
            self.errors.append(ValidationError(
                line_number=1,
                column=0,
                message="Missing version declaration",
                severity=ErrorSeverity.ERROR,
                suggestion="Add //@version=5 at the top of the script"
            ))
    
    def _check_strategy_declaration(self, lines: List[str]) -> None:
        """Check for proper strategy() declaration."""
        has_strategy = False
        has_indicator = False
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Skip comments
            if stripped.startswith('//'):
                continue
            
            if stripped.startswith('strategy(') or 'strategy(' in stripped:
                has_strategy = True
                
                # Check if strategy() spans multiple lines (ERROR)
                if stripped.startswith('strategy(') and not self._is_complete_call(stripped):
                    self.errors.append(ValidationError(
                        line_number=i + 1,
                        column=0,
                        message="strategy() call appears to span multiple lines",
                        severity=ErrorSeverity.ERROR,
                        suggestion="Put entire strategy() call on a single line"
                    ))
                break
            
            if stripped.startswith('indicator('):
                has_indicator = True
                break
        
        if not has_strategy and not has_indicator:
            self.errors.append(ValidationError(
                line_number=1,
                column=0,
                message="Missing strategy() or indicator() declaration",
                severity=ErrorSeverity.ERROR,
                suggestion="Add strategy() call after version declaration"
            ))
    
    def _check_multiline_calls(self, lines: List[str]) -> None:
        """Detect function calls that span multiple lines incorrectly."""
        
        in_multiline = False
        multiline_start = 0
        paren_depth = 0
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Skip comments and empty lines
            if not stripped or stripped.startswith('//'):
                continue
            
            # Count parentheses
            for j, char in enumerate(stripped):
                if char == '(':
                    if paren_depth == 0:
                        in_multiline = True
                        multiline_start = i
                    paren_depth += 1
                elif char == ')':
                    paren_depth -= 1
                    if paren_depth == 0:
                        in_multiline = False
            
            # Check for lines that end with comma inside parentheses (multiline call)
            if in_multiline and stripped.endswith(','):
                # Check if this is a strategy/entry/exit call
                start_line = lines[multiline_start].strip()
                for func in ['strategy(', 'strategy.entry(', 'strategy.exit(']:
                    if func in start_line:
                        self.errors.append(ValidationError(
                            line_number=i + 1,
                            column=0,
                            message=f"Line ends with comma inside {func.rstrip('(')} call",
                            severity=ErrorSeverity.ERROR,
                            suggestion="Collapse function call to a single line"
                        ))
                        break
    
    def _check_continuation_lines(self, lines: List[str]) -> None:
        """Check for invalid line continuations."""
        
        continuation_keywords = ['and', 'or', '+', '-', '*', '/', '?', ':']
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Skip comments and empty lines
            if not stripped or stripped.startswith('//'):
                continue
            
            # Check if line STARTS with a continuation keyword
            for kw in continuation_keywords:
                if stripped.startswith(kw + ' ') or stripped == kw:
                    self.errors.append(ValidationError(
                        line_number=i + 1,
                        column=0,
                        message=f"Line starts with '{kw}' which is invalid continuation",
                        severity=ErrorSeverity.ERROR,
                        suggestion=f"Move '{kw}' to the end of the previous line or combine lines"
                    ))
                    break
    
    def _check_string_literals(self, lines: List[str]) -> None:
        """Check for unclosed string literals."""
        
        for i, line in enumerate(lines):
            # Skip comments
            if line.strip().startswith('//'):
                continue
            
            # Count quotes (simple check)
            single_quotes = line.count("'") - line.count("\\'")
            double_quotes = line.count('"') - line.count('\\"')
            
            if single_quotes % 2 != 0:
                self.errors.append(ValidationError(
                    line_number=i + 1,
                    column=0,
                    message="Unclosed single quote string",
                    severity=ErrorSeverity.ERROR,
                    suggestion="Ensure all strings are properly closed"
                ))
            
            if double_quotes % 2 != 0:
                self.errors.append(ValidationError(
                    line_number=i + 1,
                    column=0,
                    message="Unclosed double quote string",
                    severity=ErrorSeverity.ERROR,
                    suggestion="Ensure all strings are properly closed"
                ))
    
    def _check_operators(self, lines: List[str]) -> None:
        """Check for common operator mistakes."""
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Skip comments
            if stripped.startswith('//'):
                continue
            
            # Check for == instead of = in assignment
            # This is tricky since == is valid for comparison
            
            # Check for single = in if conditions (might be intentional but warn)
            if re.search(r'\bif\s+.*[^=!<>]=[^=]', stripped):
                if '==' not in stripped and '!=' not in stripped:
                    self.errors.append(ValidationError(
                        line_number=i + 1,
                        column=0,
                        message="Single '=' in if condition - did you mean '=='?",
                        severity=ErrorSeverity.WARNING,
                        suggestion="Use '==' for comparison, '=' for assignment"
                    ))
    
    def _check_brackets(self, script: str) -> None:
        """Check for balanced brackets."""
        
        brackets = {'(': ')', '[': ']', '{': '}'}
        stack = []
        
        in_string = False
        string_char = None
        
        for i, char in enumerate(script):
            # Handle strings
            if char in '"\'':
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
                continue
            
            if in_string:
                continue
            
            if char in brackets:
                stack.append((char, i))
            elif char in brackets.values():
                if not stack:
                    # Find line number
                    line_num = script[:i].count('\n') + 1
                    self.errors.append(ValidationError(
                        line_number=line_num,
                        column=i,
                        message=f"Unmatched closing bracket '{char}'",
                        severity=ErrorSeverity.ERROR,
                        suggestion="Check bracket matching"
                    ))
                else:
                    open_bracket, _ = stack.pop()
                    if brackets[open_bracket] != char:
                        line_num = script[:i].count('\n') + 1
                        self.errors.append(ValidationError(
                            line_number=line_num,
                            column=i,
                            message=f"Mismatched brackets: '{open_bracket}' and '{char}'",
                            severity=ErrorSeverity.ERROR,
                            suggestion="Ensure brackets are properly matched"
                        ))
        
        # Check for unclosed brackets
        for bracket, pos in stack:
            line_num = script[:pos].count('\n') + 1
            self.errors.append(ValidationError(
                line_number=line_num,
                column=pos,
                message=f"Unclosed bracket '{bracket}'",
                severity=ErrorSeverity.ERROR,
                suggestion="Add closing bracket"
            ))
    
    def _check_common_mistakes(self, lines: List[str]) -> None:
        """Check for common Pine Script mistakes."""
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Skip comments
            if stripped.startswith('//'):
                continue
            
            # Check for Python-style comments
            if '#' in stripped and not stripped.startswith('color.'):
                # Might be a hex color, check context
                if not re.search(r'#[0-9a-fA-F]{6}', stripped):
                    self.errors.append(ValidationError(
                        line_number=i + 1,
                        column=stripped.index('#'),
                        message="Python-style comment '#' - use '//' in Pine Script",
                        severity=ErrorSeverity.ERROR,
                        suggestion="Replace '#' with '//'"
                    ))
            
            # Check for Python-style True/False
            if re.search(r'\bTrue\b', stripped):
                self.errors.append(ValidationError(
                    line_number=i + 1,
                    column=0,
                    message="Python 'True' used - Pine Script uses 'true'",
                    severity=ErrorSeverity.ERROR,
                    suggestion="Replace 'True' with 'true'"
                ))
            
            if re.search(r'\bFalse\b', stripped):
                self.errors.append(ValidationError(
                    line_number=i + 1,
                    column=0,
                    message="Python 'False' used - Pine Script uses 'false'",
                    severity=ErrorSeverity.ERROR,
                    suggestion="Replace 'False' with 'false'"
                ))
            
            # Check for Python-style None
            if re.search(r'\bNone\b', stripped):
                self.errors.append(ValidationError(
                    line_number=i + 1,
                    column=0,
                    message="Python 'None' used - Pine Script uses 'na'",
                    severity=ErrorSeverity.ERROR,
                    suggestion="Replace 'None' with 'na'"
                ))
    
    def _is_complete_call(self, line: str) -> bool:
        """Check if a function call is complete (balanced parentheses)."""
        count = 0
        for char in line:
            if char == '(':
                count += 1
            elif char == ')':
                count -= 1
        return count == 0
    
    def fix_common_issues(self, script: str) -> str:
        """
        Attempt to automatically fix common issues.
        Returns the fixed script.
        """
        lines = script.split('\n')
        fixed_lines = []
        
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # Fix lines starting with 'and' or 'or' - append to previous line
            if stripped.startswith('and ') or stripped.startswith('or '):
                if fixed_lines:
                    fixed_lines[-1] = fixed_lines[-1].rstrip() + ' ' + stripped
                    i += 1
                    continue
            
            # Fix multiline function calls ending with comma
            if stripped.endswith(',') and '(' in stripped:
                # Collect the entire multiline call
                combined = stripped
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    combined += ' ' + next_line
                    if ')' in next_line and combined.count('(') == combined.count(')'):
                        break
                    j += 1
                
                # Clean up extra whitespace
                combined = re.sub(r'\s+', ' ', combined)
                fixed_lines.append(combined)
                i = j + 1
                continue
            
            fixed_lines.append(line)
            i += 1
        
        result = '\n'.join(fixed_lines)
        
        # Fix Python-style booleans
        result = re.sub(r'\bTrue\b', 'true', result)
        result = re.sub(r'\bFalse\b', 'false', result)
        result = re.sub(r'\bNone\b', 'na', result)
        
        return result


def validate_pine_script(script: str) -> Tuple[bool, List[ValidationError]]:
    """Convenience function to validate a Pine Script."""
    validator = PineValidator()
    return validator.validate(script)


def fix_pine_script(script: str) -> str:
    """Convenience function to fix common Pine Script issues."""
    validator = PineValidator()
    return validator.fix_common_issues(script)


if __name__ == "__main__":
    # Test with a sample script
    test_script = """
//@version=5
strategy("Test Strategy",
    overlay=true,
    initial_capital=10000)

sma20 = ta.sma(close, 20)
longCondition = close > sma20
    and volume > ta.sma(volume, 20)

if longCondition
    strategy.entry("Long", strategy.long)
"""
    
    is_valid, errors = validate_pine_script(test_script)
    print(f"Valid: {is_valid}")
    for error in errors:
        print(f"  [{error.severity.value}] Line {error.line_number}: {error.message}")
        if error.suggestion:
            print(f"    Suggestion: {error.suggestion}")
    
    print("\nFixed script:")
    fixed = fix_pine_script(test_script)
    print(fixed)
