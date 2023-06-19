import os
import glob
import json
import csv
import openai
import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, String, Double, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.engine import URL

load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')


def main():
    url = URL.create(
        drivername='postgresql',
        host='localhost',
        username=os.getenv('PG_USERNAME'),
        password=os.getenv('PG_PASSWORD'),
        database=os.getenv('PG_DATABASE')
    )

    engine = create_engine(url)
    engine.connect()

    Base = declarative_base()

    class Product(Base):
        __tablename__ = 'products'

        sku = Column(String(), primary_key=True)
        manufacturer_name = Column(String())
        name = Column(String())
        qty = Column(String())
        flavour = Column(String())
        weight = Column(Double())
        img_url = Column(String())
        retail_price = Column(Double())
        description = Column(String())
        meta_title = Column(String())
        meta_description = Column(String())
        created_at = Column(DateTime, default=datetime.datetime.utcnow)
        updated_at = Column(DateTime, default=datetime.datetime.utcnow)

        #! TODO: Save OPENAI response in database

    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    csv_file = glob.glob('*.csv')[0]

    with open(csv_file, newline='') as csv_file:
        reader = csv.DictReader(csv_file, delimiter=';')

        for row in reader:
            sku = row['sku']
            manufacturer_name = row['manufacturer_name']
            name = row['name']
            qty = row['qty']
            flavour = row['flavour']
            weight = row['weight']
            img_url = row['img_url']
            retail_price = row['retail_price']

            product = session.get(Product, sku)

            if product:
                continue

            new_product = Product(
                sku=sku,
                manufacturer_name=manufacturer_name,
                name=name,
                qty=qty,
                flavour=flavour,
                weight=weight,
                img_url=img_url,
                retail_price=retail_price
            )

            session.add(new_product)
            session.commit()

    products = session.query(Product).limit(10).all()

    for product in products:
        if product.description or product.meta_title or product.meta_description:
            continue

        prompt = 'Please provide me with a JSON value containing information about a product with the following specificaitions:\n{\n"manufacturer_name":' + f""""{product.manufacturer_name}",\n"name": "{product.name}",\n"flavour": "{product.flavour}"\n""" + """}.
The JSON value should include the following properties: "description", "meta_title", "meta_description".
Please format the response as a valid JSON object with the values translated in Romanian, no other comments.
Example of a valid response:
{
    "description": "...",
    "meta_title": "...",
    "meta_description": "..."
}
"""

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        response_content = response['choices'][0]['message']['content'].strip()
        response_as_json = json.loads(response_content)

        product.description = response_as_json.get('description', '')
        product.meta_title = response_as_json.get('meta_title', '')
        product.meta_description = response_as_json.get('meta_description', '')
        product.updated_at = datetime.datetime.utcnow()

        session.commit()


if __name__ == '__main__':
    main()
