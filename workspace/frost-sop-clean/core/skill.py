"""
PHILOSOPHY:
Skill is a stateless capability unit (like a protein).
Receives context dict, returns updated context dict.
"""


class Skill:
    """
    PHILOSOPHY: A protein. Stateless capability unit.
    Receives context dict, returns updated context dict.
    """

    def __init__(self, name: str, func):
        """
        Initialize a Skill.

        Args:
            name: The name of the skill
            func: A pure function with signature func(context: dict) -> dict
        """
        self.name = name
        self._func = func

    def execute(self, context: dict) -> dict:
        """
        Execute the skill function.

        Args:
            context: The input context dictionary

        Returns:
            Updated context dictionary
        """
        return self._func(context)
