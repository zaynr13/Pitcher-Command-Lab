"""Pure plate-appearance state transitions."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Count:
    balls: int = 0
    strikes: int = 0
    ended: bool = False
    result: str = ""

    def __post_init__(self):
        if (
            type(self.balls) is not int
            or type(self.strikes) is not int
            or not 0 <= self.balls <= 3
            or not 0 <= self.strikes <= 2
        ):
            raise ValueError("Invalid live count")


def advance(c, event):
    if c.ended:
        raise ValueError("Plate appearance already ended")
    if event == "ball":
        return (
            Count(c.balls, c.strikes, True, "walk")
            if c.balls == 3
            else Count(c.balls + 1, c.strikes)
        )
    if event in ["called_strike", "whiff", "tipped_strike"]:
        return (
            Count(c.balls, c.strikes, True, "strikeout")
            if c.strikes == 2
            else Count(c.balls, c.strikes + 1)
        )
    if event == "foul":
        return Count(c.balls, min(2, c.strikes + 1))
    if event in [
        "out",
        "single",
        "double",
        "triple",
        "home_run",
        "reach_on_error",
        "fielders_choice",
    ]:
        return Count(c.balls, c.strikes, True, event)
    raise ValueError("Unsupported event")
