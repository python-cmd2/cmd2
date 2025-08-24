#!/usr/bin/env python3
"""An example of using Rich Tables within a cmd2 application for displaying tabular data.

While you can use any Python library for displaying tabular data within a cmd2 application,
we recommend using rich since that is built into cmd2.

Data comes from World Population Review: https://worldpopulationreview.com/
"""

from rich.table import Table

import cmd2

CITY_HEADERS = ['Country Flag', 'City', 'Country', '2025 Population']

CITY_DATA = [
    [
        "🇯🇵",
        "Tokyo (東京)",
        "Japan",
        37_036_200,
    ],
    [
        "🇮🇳",
        "Delhi (दिल्ली)",
        "India",
        34_665_600,
    ],
    [
        "🇨🇳",
        "Shanghai (上海)",
        "China",
        30_482_100,
    ],
    [
        "🇧🇩",
        "Dhaka (ঢাকা)",
        "Bangladesh",
        24_652_900,
    ],
    [
        "🇪🇬",
        "Cairo (القاهرة)",
        "Egypt",
        23_074_200,
    ],
    [
        "🇪🇬",
        "São Paulo",
        "Brazil",
        22_990_000,
    ],
]

COUNTRY_HEADERS = ['Flag', 'Country', '2025 Population', 'Area (M km^2)', 'Density (/km^2)']

COUNTRY_DATA = [
    [
        "🇮🇳",
        "India",
        1_463_870_000,
        3.3,
        492,
    ],
    [
        "🇨🇳",
        "China",
        1_416_100_000,
        9.7,
        150,
    ],
    [
        "🇺🇸",
        "United States",
        347_276_000,
        9.4,
        38,
    ],
    [
        "🇮🇩",
        "Indonesia",
        285_721_000,
        1.9,
        152,
    ],
    [
        "🇵🇰",
        "Pakistan",
        255_220_000,
        0.9,
        331,
    ],
    [
        "🇳🇬",
        "Nigeria",
        237_528_000,
        0.9,
        261,
    ],
]


class TableApp(cmd2.Cmd):
    """Cmd2 application to demonstrate displaying tabular data using rich."""

    TABLE_CATEGORY = 'Table Commands'

    def __init__(self) -> None:
        """Initialize the cmd2 application."""
        super().__init__()

        # Prints an intro banner once upon application startup
        self.intro = 'Are you curious which countries and cities on Earth have the largest populations?'

        # Set the default category name
        self.default_category = 'cmd2 Built-in Commands'

    @cmd2.with_category(TABLE_CATEGORY)
    def do_cities(self, _: cmd2.Statement) -> None:
        """Display the cities with the largest population."""
        table = Table(show_footer=False)
        table.title = "Largest Cities by Population 2025"
        table.caption = "Data from https://worldpopulationreview.com/"

        for header in CITY_HEADERS:
            table.add_column(header)

        for row in CITY_DATA:
            # Convert integers or floats to strings, since rich tables can not render int/float
            str_row = [f"{item:,}" if isinstance(item, int) else str(item) for item in row]
            table.add_row(*str_row)

        self.poutput(table)

    @cmd2.with_category(TABLE_CATEGORY)
    def do_countries(self, _: cmd2.Statement) -> None:
        """Display the countries with the largest population."""
        table = Table(show_footer=False)
        table.title = "Largest Countries by Population 2025"
        table.caption = "Data from https://worldpopulationreview.com/"

        for header in COUNTRY_HEADERS:
            justify = "left"
            if 'Population' in header or 'Density' in header:
                justify = "right"
            if 'Area' in header:
                justify = "center"
            table.add_column(header, justify=justify)

        for row in COUNTRY_DATA:
            # Convert integers or floats to strings, since rich tables can not render int/float
            str_row = [f"{item:,}" if isinstance(item, int) else str(item) for item in row]
            table.add_row(*str_row)

        self.poutput(table)


if __name__ == '__main__':
    app = TableApp()
    app.cmdloop()
