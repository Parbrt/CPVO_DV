import pandas as pd

def main():
    # Load csv
    dataset = pd.read_csv('data/dataset.csv')
    print(dataset.head())

if __name__ == "__main__":
    main()