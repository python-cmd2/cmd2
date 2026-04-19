#!/usr/bin/env python3
"""An example of using Rich Tables within a cmd2 application for displaying tabular data.

While you can use any Python library for displaying tabular data within a cmd2 application,
we recommend using rich since that is built into cmd2.

Data comes from World Population Review: https://worldpopulationreview.com/
and https://en.wikipedia.org/wiki/List_of_countries_by_GDP_(nominal)

NOTE: The flag emojis used require appropriate font support in your terminal
and/or IDE. Any "Nerd Font" should work. Some good options include:
- JetBrains Mono
- Fira Code
- Hack
- Monaspace
"""

from rich.table import Table

import cmd2
from cmd2.colors import Color

CITY_HEADERS = ["Flag", "City", "Country", "2025 Population"]
CITY_DATA = [
    ["🇯🇵", "Tokyo (東京)", "Japan", 37_036_200],
    ["🇮🇳", "Delhi", "India", 34_665_600],
    ["🇨🇳", "Shanghai (上海)", "China", 30_482_100],
    ["🇧🇩", "Dhaka", "Bangladesh", 24_652_900],
    ["🇪🇬", "Cairo (القاهرة)", "Egypt", 23_074_200],
    ["🇪🇬", "São Paulo", "Brazil", 22_990_000],
    ["🇲🇽", "Mexico City", "Mexico", 22_752_400],
    ["🇨🇳", "Beijing (北京)", "China", 22_596_500],
    ["🇮🇳", "Mumbai", "India", 22_089_000],
    ["🇯🇵", "Osaka (大阪)", "Japan", 18_921_600],
]
CITY_TITLE = "10 Largest Cities by Population 2025"
CITY_CAPTION = "Data from https://worldpopulationreview.com/"

COUNTRY_HEADERS = [
    "Flag",
    "Country",
    "2025 Population",
    "Area (M km^2)",
    "Population Density (/km^2)",
    "GDP (million US$)",
    "GDP per capita (US$)",
]
COUNTRY_DATA = [
    ["🇮🇳", "India", 1_463_870_000, 3.3, 492, 4_187_017, 2_878],
    ["🇨🇳", "China (中国)", 1_416_100_000, 9.7, 150, 19_231_705, 13_687],
    ["🇺🇸", "United States", 347_276_000, 9.4, 38, 30_507_217, 89_105],
    ["🇮🇩", "Indonesia", 285_721_000, 1.9, 152, 1_429_743, 5_027],
    ["🇵🇰", "Pakistan", 255_220_000, 0.9, 331, 373_072, 1_484],
    ["🇳🇬", "Nigeria", 237_528_000, 0.9, 261, 188_271, 807],
    ["🇧🇷", "Brazil", 212_812_000, 8.5, 25, 2_125_958, 9_964],
    ["🇧🇩", "Bangladesh", 175_687_000, 0.1, 1_350, 467_218, 2_689],
    ["🇷🇺", "Russia (россия)", 143_997_000, 17.1, 9, 2_076_396, 14_258],
    ["🇪🇹", "Ethiopia (እትዮጵያ)", 135_472_000, 1.1, 120, 117_457, 1_066],
]
COUNTRY_TITLE = "10 Largest Countries by Population 2025"
COUNTRY_CAPTION = "Data from https://worldpopulationreview.com/ and Wikipedia"


class TableApp(cmd2.Cmd):
    """Cmd2 application to demonstrate displaying tabular data using rich."""

    DEFAULT_CATEGORY = "Table Commands"

    def __init__(self) -> None:
        """Initialize the cmd2 application."""
        super().__init__()

        # Prints an intro banner once upon application startup
        self.intro = "Are you curious which countries and cities on Earth have the largest populations?"

    def do_cities(self, _: cmd2.Statement) -> None:
        """Display the cities with the largest population."""
        table = Table(title=CITY_TITLE, caption=CITY_CAPTION)

        for header in CITY_HEADERS:
            table.add_column(header)

        for row in CITY_DATA:
            # Convert integers or floats to strings, since rich tables can not render int/float
            str_row = [f"{item:,}" if isinstance(item, int) else str(item) for item in row]
            table.add_row(*str_row)

        self.poutput(table)

    def do_countries(self, _: cmd2.Statement) -> None:
        """Display the countries with the largest population."""
        table = Table(title=COUNTRY_TITLE, caption=COUNTRY_CAPTION)

        for header in COUNTRY_HEADERS:
            justify = "right"
            header_style = None
            style = None
            match header:
                case population if "2025 Population" in population:
                    header_style = Color.BRIGHT_BLUE
                    style = Color.BLUE
                case density if "Density" in density:
                    header_style = Color.BRIGHT_RED
                    style = Color.RED
                case percap if "per capita" in percap:
                    header_style = Color.BRIGHT_GREEN
                    style = Color.GREEN
                case flag if "Flag" in flag:
                    justify = "center"
                case country if "Country" in country:
                    justify = "left"

            table.add_column(header, justify=justify, header_style=header_style, style=style)

        for row in COUNTRY_DATA:
            # Convert integers or floats to strings, since rich tables can not render int/float
            str_row = [f"{item:,}" if isinstance(item, int) else str(item) for item in row]
            table.add_row(*str_row)

        self.poutput(table)


if __name__ == "__main__":
    app = TableApp()
    app.cmdloop()
