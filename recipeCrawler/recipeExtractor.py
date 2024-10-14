import requests
from bs4 import BeautifulSoup
import dotenv
import openai
import os

# Load envorinment variables from .env file located in ../


class RecipeExtractor:
    def __init__(self, api_key):
        self.api_key = api_key
        openai.api_key = self.api_key

    def extract_recipe_info(self, url):
        # Step 1: Scrape the webpage
        response = requests.get(url)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch the URL: {url}")

        soup = BeautifulSoup(response.content, "html.parser")

        # Step 2: Extract raw content for the LLM to process
        title = (
            soup.find("h1").get_text(strip=True)
            if soup.find("h1")
            else "No title found"
        )
        raw_text = " ".join([p.get_text(strip=True) for p in soup.find_all("p")])

        # Step 3: Use OpenAI for processing
        # Generate a short summary of the recipe
        summary_prompt = f"Here is some text from a recipe webpage: \n\n{raw_text}\n\nPlease provide a title and a short summary of this recipe.\
            The format should be: \n\nTitle: <title>\nSummary: <summary>"

        summary_response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": summary_prompt},
            ],
            max_tokens=50,
        )

        message = summary_response.choices[0].message.content

        title_chat = ""
        summary = ""

        for line in message.split("\n"):
            if line.startswith("Title:"):
                title_chat = line.split("Title:")[1].strip()
            elif line.startswith("Summary:"):
                summary = line.split("Summary:")[1].strip()

        # If the title was not found, use the title from the chat
        if title == "No title found":
            title = title_chat

        # Extract the list of ingredients
        ingredients_prompt = f"Here is some text from a recipe webpage: \n\n{raw_text}\n\nPlease provide only the names of the ingredients used in this recipe separated by commas."
        ingredients_response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": ingredients_prompt},
            ],
            max_tokens=100,
        )
        ingredients = ingredients_response.choices[0].message.content.split(",")
        ingredients = [ingredient.strip().lower() for ingredient in ingredients]
        # Remove letters and numbers from the ingredients
        ingredients = [
            ingredient
            for ingredient in ingredients
            if any(c.isalpha() for c in ingredient)
        ]
        return {
            "recipe_id": hash(url),
            "url": url,
            "title": title,
            "summary": summary,
            "ingredients": ingredients,
        }


if __name__ == "__main__":
    # Test with the provided URL

    dotenv.load_dotenv(dotenv.find_dotenv())

    url = (
        "https://www.marmiton.org/recettes/recette_cinnamon-rolls-de-karine_327467.aspx"
    )
    extractor = RecipeExtractor(api_key=os.getenv("OPENAI_API_KEY"))
    recipe_info = extractor.extract_recipe_info(url)

    # Display the extracted information
    print("Title:", recipe_info["title"])
    print("Summary:", recipe_info["summary"])
    print("Ingredients:", recipe_info["ingredients"])
