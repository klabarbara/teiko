from db import init_db, load_csv

if __name__ == "__main__":
    engine = init_db("sqlite:///cytometry.db")
    load_csv(engine, "data/cell-count.csv")
    print("✅ Database initialized and populated.")
