import discord
import requests
from requests.structures import CaseInsensitiveDict
from urllib.parse import unquote

# only read env values
from dotenv import dotenv_values
config = dotenv_values(".env")

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

# Input: MabiBase URL
# Example URL: https://na.mabibase.com/tools/auction-house?server=mabius6&q=ItemName,"Fine+Leather"&sort=ListedDate:Ascending
# Output: arr of key,value objects i.e [{'type': 'itemName', 'value': 'Fine Leather'}]
#       Type 1 - type [str], comparator [str], value [str]
#       Type 2 - type [str], value [str]
#       Type 3 - type [str], part [str], value [str]
# Description: Parses a MabiBase URL and returns key,value objects of its query parameters
def decode_url(url):
    # replace hexadecimals with their respective special charas
    url = unquote(url)
    split = url.split("?")

    # specifically get &q=...
    params = split[1].split("&")
    testing = dict(param.split("=") for param in params)
    filters = testing["q"].split(";")

    params = []

    outPath = {
        "TotalPrice": 1,
        "UnitPrice": 1,
        "ItemName": 2,
        "ItemId": 2,
        "ItemType": 2,
        "ListingType": 2,
        "ListedAfter": 2,
        "Color": 3,
        "EnchantName": 2,
        "EnchantScrollRank": 1,
        "EnchantExpiration": 2,
        "ReforgeRank": 1,
        "EquipmentRace": 2,
        "AdoptionMedalPet": 2
    }

    for filter in filters:
        itemFilter = {}
        options = filter.split(",")
        filterType = options[0] 

        if outPath[filterType] == 1:
            itemFilter['type'] = filterType
            itemFilter['comparator'] = options[1]
            itemFilter['value'] = options[2].replace('"', '')

        if outPath[filterType] == 2:
            itemFilter['type'] = filterType
            itemFilter['value'] = options[1].replace('+', ' ').replace('"', '')

        if outPath[filterType] == 3:
            itemFilter['type'] = filterType
            itemFilter['part'] = options[1]
            itemFilter['value'] = options[2].replace('"', '') 
        
        params.append(itemFilter)

    return params

# Input: list of params (output from decode_url())
# Output: lots of MabiBase API information regarding Auction House listings
#   Check example_output.json for an example
# Description: generates a post request to MabiBase graphql API to
#   retrieve filtered Auction House listing information
def post_mabibase(params):
    print(params)
    output = [
    {
        "operationName":"auctionHouseSearch",
        "variables":{
            "server":"mabius6",
            "filters": params,
            "pagination":{
                "pageSize":25,
                "pageIndex":0
            },
            "sort":{
                "attribute":"ItemName",
                "direction":"Ascending"
            }
        },
        "extensions":{
            "persistedQuery":{
                "version":1,
                "sha256Hash":"e42f50b9ab00b0e7b820afbaae91c07722178ed6b0d3aa3b578c8cc4edfe3a84"
            }
        }
    }
    ]

    url = "https://api.na.mabibase.com/graphql?"
    headers = CaseInsensitiveDict()
    headers["Content-Type"] = "application/json"
    r = requests.post(url, headers=headers, json=output)

    auctionHouse = r.json()
    listingInformation = auctionHouse[0]["data"]["auctionHouse"]["results"]

    return listingInformation

# Input: API objects (check post_mabibase() and example_output.json)
# Output: List of Discord embed objects with AH information
# Description: Parses the returned API information and returns it in a readable Discord embed
def parse_listings(listingInfo, n):
    parsedListings = []

    if len(listingInfo) <= 0:
        newEmbed = discord.Embed(
            colour = discord.Colour.random(),
            description = "Error, no items"           
        )        
        newEmbed.set_author(name = "MabiBase Alert Extended Info")
        parsedListings.append(newEmbed)
        return parsedListings

    for i in range(n):
        unitPrice = listingInfo[i]["price1"]
        totalPrice = listingInfo[i]["price2"]
        itemAmount = listingInfo[i]["itemInfo"]["info"]["amount"]
        itemName = str(listingInfo[i]["itemName"])
        iconUrl = str(listingInfo[i]["miscData"]["itemDetails"]["data"]["miscData"]["iconUrl"])

        # Pouches and Enchant Scrolls in the MabiBase API return an item amount of 0
        # todo: return the amount of items *inside* the pouch instead
        if itemAmount <= 0:
            itemAmount = 1

        unitPrice = "{:,}".format(unitPrice)
        totalPrice = "{:,}".format(totalPrice)

        newEmbed = discord.Embed(
            colour = discord.Colour.random(),
            description = itemName           
        )
        newEmbed.set_author(name = "MabiBase Alert Extended Info")
        newEmbed.set_thumbnail(url = iconUrl)
        priceField = "Per Unit: " + str(unitPrice) + "\nTotal Price: " + str(totalPrice) + "\nAmount: " + str(itemAmount)
        newEmbed.add_field(name = "Price", value = priceField)

        parsedListings.append(newEmbed)

    return parsedListings

def get_mabibase_url(listing):
    for field in listing.fields:
        if field.name == 'View New Listings':
            return field.value

def get_number_listings(listing):
    for field in listing.fields:
        if field.name == 'Number of New Listings':
            return field.value    

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.webhook_id != None:
        if len(message.embeds) != 0:
            listing = message.embeds[0]

        params = decode_url(get_mabibase_url(listing))
        resp = post_mabibase(params)
        parsedListings = parse_listings(resp, int(get_number_listings(listing)))

        await message.channel.send(embeds = parsedListings)

client.run(config["USER"])