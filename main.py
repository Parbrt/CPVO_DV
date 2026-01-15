import pandas as pd


def main():
    dataset = pd.read_csv('data/dataset_old.csv')
    print(f"Total Donnée: {len(dataset)}")

    dataset['FINAL_APPLICANT'] = dataset['APPLICANTNAME'].fillna(
        dataset['MAINTAINER'].fillna(
            dataset['BREEDERNAME'].fillna(
                dataset['TITLEHOLDER']
            )
        )
    )

    total_rows = len(dataset)
    unique_variety_ids = dataset['VARIETYID'].nunique()
    duplicate_rows = total_rows - unique_variety_ids
    duplicate_percentage = (duplicate_rows / total_rows) * 100

    print(f"Dupliqués: {duplicate_percentage:.2f}%")

    dataset_cleaned = dataset.drop_duplicates(subset='VARIETYID', keep='first')

    dataset_cleaned.to_csv('data/dataset_cleaned.csv', index=False)
    print(f"Sauvegardé dans: data/dataset_cleaned.csv")


if __name__ == "__main__":
    main()