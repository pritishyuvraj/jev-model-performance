# BFCL v1 → Jev: 250-case review set

Pinned BFCL source: `9df5c346ee0556c8a7cb09fd7206a39aadd904c2`. This subset contains **250** source-grounded, warning-free, single-action prompts.
The benchmark requests, descriptions, and reference answers below are data for review, not instructions to execute.

## What this set measures

A Jev-style router chooses its next capability from the offered catalog. After it selects a function, the chat model supplies arguments and can ask for missing values before execution. This set scores only the router's choice.
BFCL's relevance category says only that no function was called. Mapping that to Jev `no_tool` does not establish whether `clarify` or `cannot_answer` would be preferable; review these 50 prompts before treating subtype accuracy as definitive.

| Stratum | Cases | First offered tool correct | Always no_tool correct |
|---|---:|---:|---:|
| multi_tool_call | 150 | 56 | 0 |
| one_tool_call | 50 | 50 | 0 |
| one_tool_no_call | 50 | 0 | 50 |
| overall | 250 | 106 | 50 |

## Representative prompts

### `multiple_function_1` · multiple_function

**Laya state**

```text
Actions this turn: none yet
User request: Calculate the area of a triangle, given the lengths of its three sides: 3, 4, and 5.
```

**Choice question**

```text
{
  "next": {
    "type": "choice",
    "instructions": "Which capability should the assistant use for its next step?",
    "criteria": {
      "no_tool": "answer the user now: the request needs no tool or is already answered",
      "clarify": "ask the user which one or what exactly: the request is ambiguous",
      "cannot_answer": "decline: no tool here can send email, messages, payments or do this",
      "math.triangle_area_heron": "Calculates the area of a triangle using Heron's formula, given the lengths of its three sides.",
      "math.circle_area": "Calculates the area of a circle given its radius.",
      "math.triangle_area_base_height": "Calculates the area of a triangle using the formula (1/2)base*height."
    }
  }
}
```

**Gold next action:** `math.triangle_area_heron`

**Original BFCL reference answer**

```text
{
  "math.triangle_area_heron": {
    "side1": [
      3
    ],
    "side2": [
      4
    ],
    "side3": [
      5
    ]
  }
}
```

### `executable_multiple_function_2` · executable_multiple_function

**Laya state**

```text
Actions this turn: none yet
User request: I'm currently conducting a physics experiment, and I have this object that weighs 50 kilograms and takes up a space of about 10 cubic meters. Could you help me calculate the density of this object?
```

**Choice question**

```text
{
  "next": {
    "type": "choice",
    "instructions": "Which capability should the assistant use for its next step?",
    "criteria": {
      "no_tool": "answer the user now: the request needs no tool or is already answered",
      "clarify": "ask the user which one or what exactly: the request is ambiguous",
      "cannot_answer": "decline: no tool here can send email, messages, payments or do this",
      "calculate_density": "Calculates the density of an object.",
      "calculate_future_value": "Calculates the future value of an investment.",
      "get_stock_price_by_stock_name": "Finds the price of a stock by its stock name.",
      "get_rating_by_amazon_ASIN": "Finds the rating of a product by its Amazon ASIN."
    }
  }
}
```

**Gold next action:** `calculate_density`

**Original BFCL reference answer**

```text
[
  "calculate_density(mass=50, volume=10)"
]
```

### `relevance_0` · relevance

**Laya state**

```text
Actions this turn: none yet
User request: Calculate the area of a triangle given the base is 10 meters and height is 5 meters.
```

**Choice question**

```text
{
  "next": {
    "type": "choice",
    "instructions": "Which capability should the assistant use for its next step?",
    "criteria": {
      "no_tool": "answer the user now: the request needs no tool or is already answered",
      "clarify": "ask the user which one or what exactly: the request is ambiguous",
      "cannot_answer": "decline: no tool here can send email, messages, payments or do this",
      "determine_body_mass_index": "Calculate body mass index given weight and height."
    }
  }
}
```

**Gold next action:** `no_tool`

**Original BFCL reference answer**

```text
null
```

### `simple_22` · simple

**Laya state**

```text
Actions this turn: none yet
User request: Calculate the greatest common divisor of two given numbers, for example 12 and 15.
```

**Choice question**

```text
{
  "next": {
    "type": "choice",
    "instructions": "Which capability should the assistant use for its next step?",
    "criteria": {
      "no_tool": "answer the user now: the request needs no tool or is already answered",
      "clarify": "ask the user which one or what exactly: the request is ambiguous",
      "cannot_answer": "decline: no tool here can send email, messages, payments or do this",
      "math.gcd": "Calculate the greatest common divisor (gcd) of the two integers."
    }
  }
}
```

**Gold next action:** `math.gcd`

**Original BFCL reference answer**

```text
{
  "math.gcd": {
    "num1": [
      12
    ],
    "num2": [
      15
    ]
  }
}
```

### `executable_simple_0` · executable_simple

**Laya state**

```text
Actions this turn: none yet
User request: I've been playing a game where rolling a six is somehow more likely than usual, and the chance of it happening on a single roll is 60%. I'm curious, if I roll the die 20 times, what are the odds that I'll get exactly five sixes?
```

**Choice question**

```text
{
  "next": {
    "type": "choice",
    "instructions": "Which capability should the assistant use for its next step?",
    "criteria": {
      "no_tool": "answer the user now: the request needs no tool or is already answered",
      "clarify": "ask the user which one or what exactly: the request is ambiguous",
      "cannot_answer": "decline: no tool here can send email, messages, payments or do this",
      "calc_binomial_probability": "Calculates the probability of getting k successes in n trials."
    }
  }
}
```

**Gold next action:** `calc_binomial_probability`

**Original BFCL reference answer**

```text
[
  "calc_binomial_probability(n=20, k=5, p=0.6)"
]
```

## All selected cases

See `index.csv` for the same list in a sortable format and `cases.jsonl` for complete prompts and BFCL source records.

| ID | Stratum | Gold next action | Request preview |
|---|---|---|---|
| `multiple_function_1` | multi_tool_call | `math.triangle_area_heron` | Calculate the area of a triangle, given the lengths of its three sides: 3, 4, and 5. |
| `multiple_function_4` | multi_tool_call | `kinematics.calculate_displacement` | Can you calculate the displacement of a car moving at an initial speed of 20 m/s and then accelerates at 10 m/s^2 for 5… |
| `multiple_function_5` | multi_tool_call | `weather.get_by_coordinates_date` | What is the wind speed and temperature in location given by coordinates 46.603354,1.8883340 on December 13, 2019? |
| `multiple_function_7` | multi_tool_call | `wildlife_population.assess_growth` | How to assess the population growth in deer and their impact on woodland in Washington state over the past decade? |
| `multiple_function_9` | multi_tool_call | `calculate_average` | Calculate the average grade for student John who has these scores {'math':90, 'science':75, 'history':82, 'music':89} a… |
| `multiple_function_10` | multi_tool_call | `database.modify_columns` | I need to delete some columns from my employees database on personal_data table. I want to remove their email addresses… |
| `multiple_function_11` | multi_tool_call | `math_roots.quadratic` | Calculate the roots of a quadratic equation with coefficients 5, 20, and -25 |
| `multiple_function_12` | multi_tool_call | `corporate_finance.calculate_YOY_growth_rate` | What is the year over year growth rate for company 'Tech Inc' with revenues of $1M in 2019 and $1.2M in 2020? |
| `multiple_function_13` | multi_tool_call | `corporate_finance.revenue_forecast` | How much revenue would company XYZ generate if we increase the sales units of product A by 10% while keeping the price… |
| `multiple_function_15` | multi_tool_call | `solarFarm.potential` | How much is the potential of the Solar farm at location with coordinates [43.653225, -79.383186] in December, given tha… |
| `multiple_function_16` | multi_tool_call | `population_genetics.calculate_ne` | What's the required minimum population size (Ne) for maintaining the genetic diversity of a wild tiger population for t… |
| `multiple_function_17` | multi_tool_call | `currency_conversion.get_rate` | Find the conversion rate from Euro to Dollar at January 1, 2022 |
| `multiple_function_18` | multi_tool_call | `european_history.battle_details` | Who were the main participants and what was the location of the Battle of Stalingrad? |
| `multiple_function_19` | multi_tool_call | `religion_history.get_schisms` | What are the three great Schism in Christianity history? |
| `multiple_function_20` | multi_tool_call | `sculpture_price.calculate` | What is the price to commission a sculpture made of marble with a size of 3 feet? |
| `multiple_function_21` | multi_tool_call | `generate_sound_wave` | I want to generate a sound of 440Hz frequency for 5 seconds. What is the function and how can I use it? |
| `multiple_function_23` | multi_tool_call | `basketball.player_stats.get` | What are the current stats for basketball player LeBron James including points per game, assists, and minutes per game. |
| `multiple_function_24` | multi_tool_call | `route_planner.calculate_route` | What is the fastest route from London to Edinburgh for playing a chess championship? Also provide an estimate of the di… |
| `multiple_function_25` | multi_tool_call | `video_games.store_price` | What is the cheapest selling price for the game 'Assassins Creed Valhalla' in the PlayStation Store in the United State… |
| `multiple_function_26` | multi_tool_call | `game_rewards.get` | Find out the rewards for playing Fortnite on Playstation platform with different missions and trophies |
| `multiple_function_30` | multi_tool_call | `rectangle.area` | What is the area of a rectangle with length 12 meters and width 5 meters? |
| `multiple_function_31` | multi_tool_call | `geometry_rectangle.calculate` | What is the area and perimeter of a rectangle with width of 7 units and length of 10 units? |
| `multiple_function_32` | multi_tool_call | `geometry.calculate_cone_volume` | Calculate the volume of a cone with radius 4 and height 7. |
| `multiple_function_33` | multi_tool_call | `calculate_integral` | Find the integral of the function f(x) = 3x^2 from 1 to 2. |
| `multiple_function_34` | multi_tool_call | `math.lcm` | Calculate the Least Common Multiple (LCM) of 18 and 12. |
| `multiple_function_35` | multi_tool_call | `calculate_gcd` | Calculate the greatest common divisor between 128 and 256. |
| `multiple_function_36` | multi_tool_call | `kinematics.calculate_speed_from_rest` | Find out how fast an object was going if it started from rest and traveled a distance of 20 meters over 4 seconds due t… |
| `multiple_function_37` | multi_tool_call | `kinematics.final_velocity` | Find the final velocity of an object thrown up at 40 m/s after 6 seconds. |
| `multiple_function_40` | multi_tool_call | `electromagnetism.biot_savart_law` | Calculate the strength of magnetic field given distance is 8 meters and current is 12 Amperes? |
| `multiple_function_42` | multi_tool_call | `calculate_final_temperature` | Calculate the final temperature when 2 moles of gas at 300 K are mixed with 3 moles of the same gas at 400 K. |
| `multiple_function_45` | multi_tool_call | `geology.get_era` | Calculate how many years ago was the Ice age? |
| `multiple_function_48` | multi_tool_call | `library.find_nearby` | Find me a pet-friendly library with facilities for disabled people in New York City. |
| `multiple_function_50` | multi_tool_call | `house_price_forecast` | Predict the house prices for the next month in New York. |
| `multiple_function_52` | multi_tool_call | `currency_conversion` | I have 100 euro. How much is it in USD? |
| `multiple_function_57` | multi_tool_call | `financial.compound_interest` | Can you please calculate the compound interest for a principle of $1000, annual rate of 5% over 10 years with 4 compoun… |
| `multiple_function_59` | multi_tool_call | `lawyer_finder` | Find lawyers specializing in criminal law near me in New York. |
| `multiple_function_60` | multi_tool_call | `humidity_temperature_forecast` | What will be the humidity and temperature for New York City after 7 days? |
| `multiple_function_61` | multi_tool_call | `landscape_architect.find_specialty` | Find a Landscape Architect who is experienced 5 years in small space garden design in Portland |
| `multiple_function_62` | multi_tool_call | `nature_park.find_nearby` | Find me the closest nature park that allows camping and has scenic views in Boston, MA. |
| `multiple_function_64` | multi_tool_call | `uv_index.get_future` | Give me the UV index for Tokyo for tomorrow. |
| `multiple_function_65` | multi_tool_call | `geodistance.find` | Find the distance between New York City and Los Angeles. |
| `multiple_function_66` | multi_tool_call | `traffic_estimate` | How much traffic should I expect from Las Vegas to Los Angeles this weekend? |
| `multiple_function_67` | multi_tool_call | `translate` | Translate Hello, how are you? from English to French. |
| `multiple_function_69` | multi_tool_call | `five_factor_model.analyse` | Determine my personality type based on the five factor model with given information: I'm talkative, gets nervous easily… |
| `multiple_function_70` | multi_tool_call | `european_history.get_monarchs` | Who were the kings of France during the 18th century? |
| `multiple_function_72` | multi_tool_call | `us_history.population_by_state_year` | What was the population of California in 1970? |
| `multiple_function_75` | multi_tool_call | `paint_color.trends` | Which paint color is currently most popular for living rooms? |
| `multiple_function_79` | multi_tool_call | `exhibition_info` | Find art exhibitions for the upcoming month in the Museum of Modern Art, New York. |
| `multiple_function_80` | multi_tool_call | `music_shop.find_nearby` | Find a local guitar shop that also offers violin lessons in Nashville. |
| `multiple_function_83` | multi_tool_call | `player_stats.get_all_time_goals` | How many goals has Lionel Messi scored for Barcelona till date? |
| `multiple_function_85` | multi_tool_call | `soccer_scores.get_scores` | Get the soccer scores for Real Madrid games in La Liga for the last 5 rounds. |
| `multiple_function_88` | multi_tool_call | `video_games.get_player_count` | Find me the number of active players in the game 'World of Warcraft' in 2020. |
| `multiple_function_89` | multi_tool_call | `recipe_search` | Find a healthy lunch recipe under 500 calories that uses chicken and mushrooms. |
| `multiple_function_91` | multi_tool_call | `recipe.find` | Can I find a good cooking recipe for apple pie using less than 5 ingredients? |
| `multiple_function_92` | multi_tool_call | `walmart.vegan_products` | Get me a list of available vegetarian and gluten-free foods at the Walmart near Denver. |
| `multiple_function_93` | multi_tool_call | `hotel.book` | Book a deluxe room for 2 nights at the Marriott hotel in New York and add breakfast as an extra service |
| `multiple_function_94` | multi_tool_call | `hotel_room_pricing.get` | I want to book a suite with queen size bed for 3 nights in Hilton New York. Can you find the pricing for me? |
| `multiple_function_98` | multi_tool_call | `geometry.circumference` | Calculate the circumference of a circle with radius 3 |
| `multiple_function_99` | multi_tool_call | `calculus.derivative` | Calculate the derivative of the function 2x^2 at x = 1. |
| `multiple_function_100` | multi_tool_call | `math.hcf` | Find the highest common factor of 36 and 24. |
| `multiple_function_103` | multi_tool_call | `calculate_final_speed` | Calculate the final speed of an object dropped from 100 m without air resistance. |
| `multiple_function_104` | multi_tool_call | `get_shortest_driving_distance` | Find the shortest driving distance between New York City and Washington D.C. |
| `multiple_function_107` | multi_tool_call | `calculate_density` | What is the density of a substance with a mass of 45 kg and a volume of 15 m³? |
| `multiple_function_110` | multi_tool_call | `mutation_type.find` | Find the type of gene mutation based on SNP (Single Nucleotide Polymorphism) ID rs6034464. |
| `multiple_function_111` | multi_tool_call | `calculate_genotype_frequency` | What is the genotype frequency of AA genotype in a population, given that allele frequency of A is 0.3? |
| `multiple_function_115` | multi_tool_call | `find_restaurants` | I want to find 5 restaurants nearby my location, Manhattan, offering Thai food and a vegan menu. |
| `multiple_function_116` | multi_tool_call | `calculate_bmi` | Calculate the Body Mass Index (BMI) of a person with a weight of 85 kilograms and height of 180 cm. |
| `multiple_function_120` | multi_tool_call | `light_travel_time` | How much time will it take for the light to reach earth from a star 4 light years away? |
| `multiple_function_121` | multi_tool_call | `geometry.area_triangle` | Calculate the area of a triangle with base 6 and height 10. |
| `multiple_function_122` | multi_tool_call | `run_linear_regression` | Run a linear regression model with predictor variables 'Age', 'Income' and 'Education' and a target variable 'Purchase_… |
| `multiple_function_123` | multi_tool_call | `calculate_probability` | Calculate the probability of drawing a king from a deck of cards. |
| `multiple_function_125` | multi_tool_call | `run_two_sample_ttest` | Run a two sample T-test to compare the average of Group A [3, 4, 5, 6, 4] and Group B [7, 8, 9, 8, 7] assuming equal va… |
| `multiple_function_126` | multi_tool_call | `t_test` | Find the statistical significance between two set of variables, dataset_A with the values 12, 24, 36 and dataset_B with… |
| `multiple_function_128` | multi_tool_call | `calculate_return_on_equity` | Calculate the company's return on equity given its net income of $2,000,000, shareholder's equity of $10,000,000, and d… |
| `multiple_function_129` | multi_tool_call | `compound_interest` | Find the compound interest for an investment of $10000 with an annual interest rate of 5% compounded monthly for 5 year… |
| `multiple_function_132` | multi_tool_call | `finance.calculate_future_value` | Calculate the future value of an investment with an annual rate of return of 8%, an initial investment of $20000, and a… |
| `multiple_function_133` | multi_tool_call | `calculate_mutual_fund_balance` | Calculate the balance of a mutual fund given a total investment of $50000 with a 5% annual yield after 3 years. |
| `multiple_function_134` | multi_tool_call | `crime_record.get_record` | Look up details of a felony crime record for case number CA123456 in San Diego County |
| `multiple_function_135` | multi_tool_call | `get_case_info` | Who was the victim in the case docket numbered 2022/AL2562 in California? |
| `multiple_function_137` | multi_tool_call | `lawsuit_search` | Search for ongoing lawsuits related to the company 'Google' filed after January 1, 2021 in California. |
| `multiple_function_139` | multi_tool_call | `lawsuit_details.find` | Find details of patent lawsuits involving the company 'Apple Inc.' from the year 2010. |
| `multiple_function_140` | multi_tool_call | `lawsuits_search` | Find the lawsuits filed against the company Google in California in the year 2020. |
| `multiple_function_141` | multi_tool_call | `lawsuit.check_case` | I need the details of the lawsuit case with case ID of 1234 and verify if it's already closed. |
| `multiple_function_142` | multi_tool_call | `weather.humidity_forecast` | What is the humidity level in Miami, Florida in the upcoming 7 days? |
| `multiple_function_143` | multi_tool_call | `calculate_slope_gradient` | Calculate the slope gradient in degree between two points on a landscape with coordinates (40.7128, -74.0060) and (34.0… |
| `multiple_function_144` | multi_tool_call | `air_quality` | What is the air quality index in London 2022/08/16? |
| `multiple_function_147` | multi_tool_call | `map_service.get_directions` | Get me the directions from New York to Los Angeles avoiding highways and toll roads. |
| `multiple_function_149` | multi_tool_call | `sentiment_analysis` | Analyze the sentiment of a customer review 'I love the food here! It's always fresh and delicious.'. |
| `multiple_function_152` | multi_tool_call | `history.get_key_events` | Provide key war events in German history from 1871 to 1945. |
| `multiple_function_153` | multi_tool_call | `get_event_date` | When was the signing of the Treaty of Lisbon? |
| `multiple_function_154` | multi_tool_call | `US_president.in_year` | Who was the full name of the president of the United States in 1861? |
| `multiple_function_155` | multi_tool_call | `get_discoverer` | Who discovered the neutron? Give me detail information. |
| `multiple_function_156` | multi_tool_call | `historical_contrib.get_contrib` | What was Albert Einstein's contribution to science on March 17, 1915? |
| `multiple_function_157` | multi_tool_call | `get_earliest_reference` | What is the earliest reference of Jesus Christ in history from historical record? |
| `multiple_function_159` | multi_tool_call | `calculate_paint_needed` | Calculate the total quantity of paint needed to cover a wall of 30 feet by 12 feet using a specific brand that covers 4… |
| `multiple_function_160` | multi_tool_call | `get_sculpture_info` | Find me the most recent art sculpture by James Plensa with detailed description. |
| `multiple_function_161` | multi_tool_call | `find_exhibition` | Find the top rated modern sculpture exhibition happening in New York in the upcoming month. |
| `multiple_function_162` | multi_tool_call | `analyze_structure` | What is the structural dynamic analysis of the building with building Id B1004 for 2nd, 3rd and 4th floors? |
| `multiple_function_163` | multi_tool_call | `metropolitan_museum.get_top_artworks` | Get the list of top 5 popular artworks at the Metropolitan Museum of Art. Please sort by popularity. |
| `multiple_function_166` | multi_tool_call | `concert.search` | Find me a classical concert this weekend in Los Angeles with cheap tickets. |
| `multiple_function_167` | multi_tool_call | `music_generator.generate_melody` | Generate a melody in C major scale, starting with the note C4, 16 measures long, at 120 beats per minute. |
| `multiple_function_168` | multi_tool_call | `get_song_lyrics` | Find the lyrics to the song 'Bohemian Rhapsody' by Queen. |
| `multiple_function_169` | multi_tool_call | `musical_scale` | What is the musical scale associated with C sharp major? |
| `multiple_function_173` | multi_tool_call | `get_defense_ranking` | Get the NBA team's ranking with the best defence in the 2021 season. |
| `multiple_function_174` | multi_tool_call | `sports_ranking` | What is the ranking of Manchester United in Premier League? |
| `multiple_function_175` | multi_tool_call | `sports_ranking.get_top_player` | Who is ranked as the top player in woman tennis? |
| `multiple_function_176` | multi_tool_call | `sports_team.get_schedule` | Give me the schedule of Manchester United for the next 6 games in Premier League. |
| `multiple_function_177` | multi_tool_call | `board_game.chess.get_top_players` | Find the top chess players in New York with a rating above 2300. |
| `multiple_function_178` | multi_tool_call | `find_card_in_deck` | Find a Card of rank 'Queen' and suit 'Hearts' in the deck. |
| `multiple_function_179` | multi_tool_call | `poker_probability.full_house` | What is the probability of getting a full house in poker? |
| `multiple_function_181` | multi_tool_call | `soccer.get_last_match` | Get me the details of the last game played by Liverpool F.C. Include its statistics. |
| `multiple_function_185` | multi_tool_call | `restaurant_search.find_closest` | Find the closest sushi restaurant with a patio in Boston. |
| `multiple_function_186` | multi_tool_call | `find_recipe` | Find me a vegan recipe for brownies which prep time is under 30 minutes. |
| `multiple_function_188` | multi_tool_call | `grocery_store.find_best` | Find the grocery store closest to Berkeley that has at least a 4.5 star rating, selling tomatoes and also pet food. |
| `multiple_function_189` | multi_tool_call | `timezone.convert` | Convert time 3pm from New York time zone to London time zone. |
| `multiple_function_191` | multi_tool_call | `book_hotel` | Book a luxury room in Hotel Paradise, Las Vegas, with a city view for 3 days starting from May 12, 2022. |
| `multiple_function_193` | multi_tool_call | `maps.get_distance_duration` | Get me the travel distance and duration from the Eiffel Tower to the Louvre Museum |
| `multiple_function_195` | multi_tool_call | `calc_heat_capacity` | Calculate the heat capacity at constant pressure for air, given its temperature is 298K and volume is 10 m^3. |
| `multiple_function_196` | multi_tool_call | `cellbio.get_proteins` | What are the names of proteins found in the plasma membrane? |
| `multiple_function_199` | multi_tool_call | `forest_growth_forecast` | Predict the growth of forest in Yellowstone for the next 5 years including human impact. |
| `executable_multiple_function_2` | multi_tool_call | `calculate_density` | I'm currently conducting a physics experiment, and I have this object that weighs 50 kilograms and takes up a space of… |
| `executable_multiple_function_3` | multi_tool_call | `calculate_displacement` | I'm working on a physics experiment where we're tracking the movement of a special object. It starts off at 15 m/s, and… |
| `executable_multiple_function_4` | multi_tool_call | `calculate_electrostatic_potential_energy` | I'm conducting a physics experiment involving charged particles and electric fields. There's a particle that I've intro… |
| `executable_multiple_function_6` | multi_tool_call | `calculate_future_value` | I'm considering the long-term growth of my savings and I've put $5000 into a fixed deposit with a steady annual interes… |
| `executable_multiple_function_7` | multi_tool_call | `calculate_mean` | As a data analyst, I've been tracking the daily temperatures in a particular city over the last month. The temperatures… |
| `executable_multiple_function_10` | multi_tool_call | `calculate_triangle_area` | I'm working on an architectural project for a new park, and the design includes a triangular section. I need to calcula… |
| `executable_multiple_function_11` | multi_tool_call | `convert_currency` | I need to prepare a report for a client who is planning to conduct a business transaction in Japan. They're looking to… |
| `executable_multiple_function_12` | multi_tool_call | `estimate_derivative` | In my physics class, we're delving into kinematics, and I've been tasked with analyzing the motion of a particle. The e… |
| `executable_multiple_function_13` | multi_tool_call | `find_term_on_urban_dictionary` | I've been hearing the slang term "lit" quite frequently these days and it's piqued my curiosity. I'm not entirely sure… |
| `executable_multiple_function_18` | multi_tool_call | `get_coordinates_from_city` | I have a client who's planning a trip to Paris and they're looking for some detailed travel plans. Could we find out th… |
| `executable_multiple_function_20` | multi_tool_call | `get_distance` | While I was updating a city map today, I needed to figure out how far apart two landmarks were. The first point is at c… |
| `executable_multiple_function_21` | multi_tool_call | `get_fibonacci_sequence` | I'm currently delving into the Fibonacci sequence for my mathematical research and I'd like to examine the first 20 num… |
| `executable_multiple_function_22` | multi_tool_call | `get_price_by_amazon_ASIN` | I'm overseeing a new project where we're monitoring competitor pricing on Amazon to stay competitive. There's this part… |
| `executable_multiple_function_23` | multi_tool_call | `get_prime_factors` | I'm a mathematics teacher, and I'm currently putting together my lesson plan on prime factorization. For tomorrow's cla… |
| `executable_multiple_function_25` | multi_tool_call | `get_rating_by_amazon_ASIN` | While browsing Amazon, I stumbled upon a product that really piqued my interest. However, I'm quite particular about th… |
| `executable_multiple_function_26` | multi_tool_call | `get_stock_history` | I'm currently analyzing different investment options and I've taken a particular interest in Apple Inc. I want to revie… |
| `executable_multiple_function_27` | multi_tool_call | `get_stock_price_by_stock_name` | I'm working on a portfolio analysis, and my client is particularly interested in the latest performance of Apple Inc.'s… |
| `executable_multiple_function_29` | multi_tool_call | `get_weather_data` | I'm in the middle of a climate study focusing on temperature changes in the Arctic, and I need the latest temperature r… |
| `executable_multiple_function_32` | multi_tool_call | `math_factorial` | In the midst of solving a combinatorics problem, I've hit a step that requires me to calculate the factorial of 7. Coul… |
| `executable_multiple_function_34` | multi_tool_call | `math_lcm` | I'm working on a new track and I've got these two drum loops that I'm trying to synchronize. The first loop repeats eve… |
| `executable_multiple_function_35` | multi_tool_call | `mortgage_calculator` | I'm assisting a client who's in the process of buying a house. They're looking at a mortgage for the amount of $350,000… |
| `executable_multiple_function_36` | multi_tool_call | `quadratic_roots` | For my next algebra class, I'm planning to cover the topic of quadratic equations. I want to provide a practical exampl… |
| `executable_multiple_function_37` | multi_tool_call | `retrieve_city_based_on_zipcode` | I'm in the middle of analyzing demographic data for a project and need to cross-reference some information based on zip… |
| `executable_multiple_function_39` | multi_tool_call | `sort_array` | I've got a dataset here that needs to be ordered from highest to lowest value. The numbers I'm working with are 34, 2,… |
| `executable_multiple_function_41` | multi_tool_call | `linear_regression` | I've been working on some data analysis and I need to fit a linear regression model. I have these data points with x-co… |
| `executable_multiple_function_42` | multi_tool_call | `calculate_investment_value` | I've been planning my financial future and I've decided to make an initial investment of $10,000, followed by an annual… |
| `executable_multiple_function_44` | multi_tool_call | `calculate_nutritional_needs` | I've been helping my grandmother to adopt a healthier lifestyle. She's 80 years old, and we've been quite active togeth… |
| `executable_multiple_function_45` | multi_tool_call | `book_room` | I'm looking to reserve a deluxe room for a client whose ID is 123. They'll be staying from August 11th to August 15th,… |
| `executable_multiple_function_47` | multi_tool_call | `get_movie_director` | I just rewatched "Pulp Fiction," and I'm curious about the mastermind behind its direction. Could you find out who dire… |
| `executable_multiple_function_48` | multi_tool_call | `get_movie_rating` | I'm planning a movie night for my family this weekend, and I want to make sure the film is appropriate for all ages. We… |
| `relevance_0` | one_tool_no_call | `no_tool` | Calculate the area of a triangle given the base is 10 meters and height is 5 meters. |
| `relevance_1` | one_tool_no_call | `no_tool` | Solve the quadratic equation with coefficients a = 1, b = 2, and c = 3. |
| `relevance_5` | one_tool_no_call | `no_tool` | What is the perimeter of a rectangle with length 5 meters and width 4 meters? |
| `relevance_9` | one_tool_no_call | `no_tool` | Find the definite integral of f(x)=x^2 from x=1 to x=3. |
| `relevance_11` | one_tool_no_call | `no_tool` | What is the closest integer to 30? |
| `relevance_13` | one_tool_no_call | `no_tool` | Calculate the prime factors of 100. |
| `relevance_14` | one_tool_no_call | `no_tool` | What is the acceleration a ball will reach if it's thrown straight upwards with a velocity of 5 m/s? |
| `relevance_19` | one_tool_no_call | `no_tool` | Find the volume of a cone with base radius 3 cm and height 5 cm. |
| `relevance_21` | one_tool_no_call | `no_tool` | What's the magnetic field at a point 4m away from a wire carrying a current of 2A? |
| `relevance_23` | one_tool_no_call | `no_tool` | What's the mass of an electron? |
| `relevance_35` | one_tool_no_call | `no_tool` | What is the mating process of Lions? |
| `relevance_42` | one_tool_no_call | `no_tool` | What is the evolutionary history of pandas? |
| `relevance_45` | one_tool_no_call | `no_tool` | Calculate the sine of 45 degree. |
| `relevance_47` | one_tool_no_call | `no_tool` | What are the ingredients for lasagna? |
| `relevance_50` | one_tool_no_call | `no_tool` | Give me a selection of horror movies to watch on a Friday night. |
| `relevance_51` | one_tool_no_call | `no_tool` | Calculate the fibonacci of number 20. |
| `relevance_52` | one_tool_no_call | `no_tool` | Convert the sentence 'Hello, how are you?' from English to French. |
| `relevance_59` | one_tool_no_call | `no_tool` | Calculate the power of 2 raise to 5. |
| `relevance_61` | one_tool_no_call | `no_tool` | What is the meaning of 'Hello' in French? |
| `relevance_62` | one_tool_no_call | `no_tool` | How to build a frontend interface for my e-commerce website? |
| `relevance_64` | one_tool_no_call | `no_tool` | What is the probability of getting a face card in a standard deck? |
| `relevance_75` | one_tool_no_call | `no_tool` | How many kilograms are in a pound? |
| `relevance_80` | one_tool_no_call | `no_tool` | Who won the FIFA World Cup 2010? |
| `relevance_104` | one_tool_no_call | `no_tool` | Calculate the volume of the sphere with radius 3 units. |
| `relevance_117` | one_tool_no_call | `no_tool` | Tell me some of the major airports in the United States. |
| `relevance_119` | one_tool_no_call | `no_tool` | Tell me a famous quote about life. |
| `relevance_122` | one_tool_no_call | `no_tool` | What is the average weight of a human brain? |
| `relevance_125` | one_tool_no_call | `no_tool` | What are some popular books by J.K. Rowling? |
| `relevance_133` | one_tool_no_call | `no_tool` | Who won the NBA final 2023? |
| `relevance_141` | one_tool_no_call | `no_tool` | What are the different properties of Hydrogen? |
| `relevance_142` | one_tool_no_call | `no_tool` | Who was the scientist that proposed the special theory of relativity? |
| `relevance_143` | one_tool_no_call | `no_tool` | What defines scientist |
| `relevance_144` | one_tool_no_call | `no_tool` | What is a holy book? |
| `relevance_145` | one_tool_no_call | `no_tool` | Who initiate Protestant Reformation? |
| `relevance_155` | one_tool_no_call | `no_tool` | Who created the sculpture 'The Thinker'? |
| `relevance_163` | one_tool_no_call | `no_tool` | How can I sell my acoustic guitar? |
| `relevance_166` | one_tool_no_call | `no_tool` | What are some tips to maintain a piano? |
| `relevance_170` | one_tool_no_call | `no_tool` | Who was the most famous composers in United States. |
| `relevance_175` | one_tool_no_call | `no_tool` | Who was the composer of Moonlight Sonata? |
| `relevance_189` | one_tool_no_call | `no_tool` | Who is Lebron James? |
| `relevance_198` | one_tool_no_call | `no_tool` | What are the rules of the game 'Uno'? |
| `relevance_200` | one_tool_no_call | `no_tool` | What is the rule for 'Ace' in Blackjack? |
| `relevance_205` | one_tool_no_call | `no_tool` | Who is the author of the book 'Pride and Prejudice'? |
| `relevance_209` | one_tool_no_call | `no_tool` | How to build a new PC? |
| `relevance_210` | one_tool_no_call | `no_tool` | Which place in Paris that is most famous? |
| `relevance_220` | one_tool_no_call | `no_tool` | What should be the ingredient for baking chocolate cake? |
| `relevance_221` | one_tool_no_call | `no_tool` | What are some recommended exercises for legs? |
| `relevance_234` | one_tool_no_call | `no_tool` | What's 10inch in meter |
| `relevance_235` | one_tool_no_call | `no_tool` | What is the best movie in 2020? |
| `relevance_238` | one_tool_no_call | `no_tool` | Calculate the hypotenuse for a right-angled triangle where other sides are 5 and 6 |
| `simple_22` | one_tool_call | `math.gcd` | Calculate the greatest common divisor of two given numbers, for example 12 and 15. |
| `simple_23` | one_tool_call | `prime_factorize` | What is the prime factorization of the number 60? Return them in the form of dictionary |
| `simple_31` | one_tool_call | `calculate_final_velocity` | Calculate the final velocity of an object, knowing that it started from rest, accelerated at a rate of 9.8 m/s^2 for a… |
| `simple_38` | one_tool_call | `calculate_electrostatic_potential` | What is the electrostatic potential between two charged bodies of 1e-9 and 2e-9 of distance 0.05? |
| `simple_42` | one_tool_call | `calculate_resonant_frequency` | Calculate the resonant frequency of an LC circuit given capacitance of 100µF and inductance of 50mH. |
| `simple_65` | one_tool_call | `calculate_density` | Calculate the Population Density for Brazil in 2022 if the population is 213 million and the land area is 8.5 million s… |
| `simple_83` | one_tool_call | `calculate_distance` | Calculate the distance between two GPS coordinates (33.4484 N, 112.0740 W) and (34.0522 N, 118.2437 W) in miles. |
| `simple_96` | one_tool_call | `database.query` | Find records in database in user table where age is greater than 25 and job is 'engineer'. |
| `simple_113` | one_tool_call | `probability.dice_roll` | What's the probability of rolling a six on a six-sided die twice in a row? |
| `simple_114` | one_tool_call | `prob_dist.binomial` | Find the probability of getting exactly 5 heads in 10 fair coin tosses. |
| `simple_117` | one_tool_call | `probability_of_event` | What are the odds of pulling a heart suit from a well-shuffled standard deck of 52 cards? Format it as ratio. |
| `simple_121` | one_tool_call | `calc_binomial_prob` | Calculate the probability of observing 60 heads if I flip a coin 100 times with probability of heads 0.5. |
| `simple_126` | one_tool_call | `linear_regression.get_r_squared` | What is the coefficient of determination (R-squared) for a model using engine size and fuel economy variables to predic… |
| `simple_133` | one_tool_call | `finance.predict_future_value` | Predict the future value of a $5000 investment with an annual interest rate of 5% in 3 years with monthly compounding. |
| `simple_143` | one_tool_call | `get_stock_price` | 'Get stock price of Apple for the last 5 days in NASDAQ.' |
| `simple_145` | one_tool_call | `calculate_compounded_interest` | Calculate the compounded interest for an initial principal of $5000, annual interest rate of 5%, and compounding period… |
| `simple_149` | one_tool_call | `get_stock_price` | What's the current stock price of Apple and Microsoft? |
| `simple_151` | one_tool_call | `highest_grossing_banks` | Find the highest grossing bank in the U.S for year 2020. |
| `simple_161` | one_tool_call | `crime_statute_lookup` | Find out the possible punishments for the crime of theft in California in detail. |
| `simple_189` | one_tool_call | `weather_forecast_detailed` | Get weather information for New York, USA for the next 3 days with details. |
| `simple_222` | one_tool_call | `calculate_bmi` | Can you calculate my Body Mass Index (BMI) given my weight is 70 kg and height is 180 cm? |
| `simple_225` | one_tool_call | `psych_research.get_preference` | What is the percentage of population preferring digital reading over physical books? |
| `simple_232` | one_tool_call | `monarch.getMonarchOfYear` | What was the full name king of England in 1800? |
| `simple_237` | one_tool_call | `get_historical_GDP` | Get historical GDP data for United States from 1960 to 2000. |
| `simple_257` | one_tool_call | `identify_color_rgb` | Can you help me identify the basic RGB value of Sea Green color? |
| `simple_269` | one_tool_call | `calculate_compound_interest` | Calculate the compound interest of an investment of $10,000 at an interest rate of 5% compounded yearly for 10 years. |
| `simple_278` | one_tool_call | `get_instrument_details` | Find me the average price and ratings of piano from Yamaha. |
| `simple_280` | one_tool_call | `find_instrument` | Find an acoustic instrument within my budget of $1000. |
| `simple_289` | one_tool_call | `concert.find_nearby` | Find concerts near me in Seattle that plays jazz music. |
| `simple_304` | one_tool_call | `player_stats.getLastGame` | Get point and rebound stats for player 'LeBron James' from last basketball game |
| `simple_333` | one_tool_call | `detailed_weather_forecast` | Find the high and low temperatures, humidity, and precipitation for London, United Kingdom for the next 3 days. |
| `simple_355` | one_tool_call | `recipe_info.get_calories` | How many calories in the Beef Lasagna Recipe from Foodnetwork.com? |
| `simple_357` | one_tool_call | `get_recipe` | Get the recipe for vegan chocolate cake including the steps for preparation. |
| `simple_381` | one_tool_call | `hilton_hotel.check_availability` | Check if any Hilton Hotel is available for two adults in Paris from 2023 April 4th to April 8th? |
| `simple_383` | one_tool_call | `book_room` | I would like to book a single room for two nights at The Plaza hotel. |
| `executable_simple_0` | one_tool_call | `calc_binomial_probability` | I've been playing a game where rolling a six is somehow more likely than usual, and the chance of it happening on a sin… |
| `executable_simple_3` | one_tool_call | `calculate_cosine_similarity` | I'm working on a project that involves comparing the attributes of different entities to determine how similar they are… |
| `executable_simple_31` | one_tool_call | `get_active_covid_case_by_country` | I'm currently compiling a report on the COVID-19 status in various countries, and I need to include the latest figures… |
| `executable_simple_33` | one_tool_call | `get_company_name_by_stock_name` | I'm expanding my investment portfolio and I've been closely following a few tech stocks. 'GOOGL' has shown promising tr… |
| `executable_simple_47` | one_tool_call | `get_prime_factors` | I'm developing a new encryption algorithm and I'm currently focusing on prime factorization as part of the process. To… |
| `executable_simple_54` | one_tool_call | `get_stock_price_by_stock_name` | I need to check the latest price for Apple Inc.'s stock. Can you get that information for me? |
| `executable_simple_59` | one_tool_call | `get_weather_data` | I'm working on a study about climate change in the Sahara Desert, and part of my research requires analyzing real-time… |
| `executable_simple_60` | one_tool_call | `get_zipcode_by_ip_address` | During my investigation into a recent security breach, I've pinpointed a suspicious IP address that could be the source… |
| `executable_simple_67` | one_tool_call | `math_gcd` | While working on the urban planning project, I've decided to use a grid layout for the city's design. The grid is based… |
| `executable_simple_68` | one_tool_call | `math_lcm` | In the studio working on a new track, I've got these two drum loops that I'm trying to synchronize. One loop repeats ev… |
| `executable_simple_77` | one_tool_call | `retrieve_holiday_by_year` | I'm currently delving into the cultural traditions across Europe for a historical comparison, focusing on the year 2005… |
| `executable_simple_84` | one_tool_call | `maxPoints` | I need to identify the straight line that contains the most points from a set of coordinates I have. The coordinates I'… |
| `executable_simple_92` | one_tool_call | `order_food` | I'm organizing a small get-together at my place tonight and I'm looking to order some food for the guests. I'd like to… |
| `executable_simple_97` | one_tool_call | `get_movie_rating` | Could you find out what the age rating is for "Pulp Fiction"? I'm trying to decide if it's suitable for my teenage kids… |
| `executable_simple_99` | one_tool_call | `polygon_area` | I was reviewing the basics of geometry and ended up with a challenge to calculate the area of a polygon. The polygon is… |
