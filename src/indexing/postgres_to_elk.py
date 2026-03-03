import os
import pandas as pd
from sqlalchemy import create_engine
from elasticsearch import Elasticsearch, helpers
from dotenv import load_dotenv

load_dotenv()

ELK_ENDPOINT = os.getenv("ELK_ENDPOINT")
ELK_API_KEY = os.getenv("ELK_API_KEY")

host = os.getenv("POSTGRES_HOST", "localhost")
port = os.getenv("POSTGRES_PORT", "5433")
user = os.getenv("POSTGRES_USER", "datalake_user")
password = os.getenv("POSTGRES_PASSWORD", "datalake_pass")
database_name = os.getenv("POSTGRES_DB", "datalake")
engine = create_engine(
		f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database_name}"
)

INTERVAL = '5 minutes'

ELK_INDEX = "finance"

client = Elasticsearch(
    hosts=[ELK_ENDPOINT],
    api_key=ELK_API_KEY
)

def generate_docs(df):
    for idx, row in df.iterrows():
        doc = row.to_dict()
        _id = doc["ts_minute_utc"].strftime("%Y-%m-%d %H:%M:%S")
        # Convertir les timestamps en string ISO
        for key, value in doc.items():
            if isinstance(value, pd.Timestamp):
                doc[key] = value.isoformat()
            elif pd.isna(value):
                doc[key] = None                
        yield {
            "_id": _id,
            "_source": doc
        }
        
def ingest_last_data(interval: str):
    
    query = f"""
      SELECT *
      FROM btc_nasdaq.mart_btc_ndx_5m_enriched
      WHERE ts_minute_utc > NOW() - INTERVAL '{interval}';
    """
    df = pd.read_sql_query(query, engine)
    
    if df.empty:
        print("No data fetched: The Exchange is closed!")
        return
    records = generate_docs(df)
    try:
        success, _ = helpers.bulk(client, records, index=ELK_INDEX)
        print(f"\n{success} records indexed from {database_name}.\n")
    except Exception as e:
        print("\n=== EXCEPTION THROWN ===")
        print(type(e), e)
        if hasattr(e, "errors"):
            print(e.errors[:7])
            print("\n=== ERROR DISPLAYED ABOVE ===\n")
            raise e
        
if __name__ == "__main__":
    ingest_last_data(INTERVAL)