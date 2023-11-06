import os
import glob
import json
import csv
import openai
import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, String, Double, DateTime, Integer
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.engine import URL
from sqlalchemy.dialects.postgresql import JSONB

load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')


def generate_product_category(product):
    if product.category:
        print('Product already has a category', product.category)
        return product.category

    prompt = '''Strictly generate product category as an JSON respecting the given JSON structure {"category": <one of the value of [Proteine, Aminoacizi, Vitamine si Minerale, Batoane si Gustari Fitness, Suplimente pentru slabit, Performanta/Stimulatoare, Pre-Workout, Creatina, Imbracaminte si acesorii pentru sala, Masa musculara, Suplimente, Probiotice]>}
Product input: 
Manufacturer: ''' + product.manufacturer_name + '''
Name: ''' + product.name
    print('Prompt', prompt)

    response = None

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system",
                 "content": "You are a fitness nutrition marketing specialist."},
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.2,
            frequency_penalty=0.5,
            max_tokens=200,
            request_timeout=5,
        )
    except Exception as e:
        print('Error generating product category', e)
        return None

    print('Response', response)

    product.openai_response = response
    product.total_tokens = response['usage']['total_tokens']

    response_content = response['choices'][0]['message']['content']
    print('Response content', response_content)

    response_as_json = json.loads(response_content)
    return response_as_json.get('category', '')


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
        weight = Column(String())
        img_url = Column(String())
        retail_price = Column(Double())
        description = Column(String())
        meta_title = Column(String())
        meta_description = Column(String())
        created_at = Column(DateTime, default=datetime.datetime.utcnow)
        updated_at = Column(DateTime, default=datetime.datetime.utcnow)
        openai_response = Column(JSONB)
        total_tokens = Column(Integer)
        category = Column(String())

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
            img_url = row['img_url']
            retail_price = row['retail_price']

            product = session.get(Product, sku)

            if product:
                product.qty = qty
                product.category = generate_product_category(product)
                session.commit()
                continue

            new_product = Product(
                sku=sku,
                manufacturer_name=manufacturer_name,
                name=name,
                qty=qty,
                flavour=flavour,
                img_url=img_url,
                retail_price=retail_price,
            )

            new_product.category = generate_product_category(new_product)
            session.add(new_product)
            session.commit()

    products = session.query(Product).all()

    for product in products:
        if product.description and product.meta_title and product.meta_description:
            continue

        prompt = """Generate product details using Romanian language and respecting the given JSON structure {"html_description":<formatted string min 600 tokens max 900 tokens>, "meta_title":  <string no more than 25 tokens length>, "meta_description": <string no more than 55 tokens length>, "weight": "<string>"}. 
Product details input:
""" + f""""{product.manufacturer_name}",\n"name": "{product.name}",\n"flavour": "{product.flavour}"\n""" + """
Output:"""
        print('Prompt', prompt)

        response = None
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system",
                        "content": "You are a fitness nutrition marketing specialist."},
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                frequency_penalty=0.5,
                max_tokens=750,
                request_timeout=15,
            )
        except Exception as e:
            print('Error generating product details', e)
            continue

        print('Response', response)

        product.openai_response = response
        product.total_tokens = response['usage']['total_tokens']

        response_content = response['choices'][0]['message']['content'].strip()
        print('Response content', response_content)

        response_as_json = json.loads(response_content)

        product.description = response_as_json.get(
            'html_description', response_as_json.get('descriere', ''))
        product.meta_title = response_as_json.get(
            'meta_title', response_as_json.get('meta_titlu', ''))
        product.meta_description = response_as_json.get(
            'meta_description', response_as_json.get('meta_descriere', ''))
        product.weight = response_as_json.get('weight', '')
        product.updated_at = datetime.datetime.utcnow()

        session.commit()


if __name__ == '__main__':
    main()
