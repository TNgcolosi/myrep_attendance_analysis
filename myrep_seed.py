# -*- coding: utf-8 -*-
"""
Created on Thu Jan 16 11:39:00 2025

@author: Thandi
"""

import pandas as pd
import re
import sqlite3
import pdfplumber
import os
db_path = "council_data.db"
connection = sqlite3.connect(db_path)

#%%
# Define function to extract names and details based on the PRESENT/ABSENT sections for Councillors only
def extract_attendees(text):
    sections = {
        "Councillors": {"Present": [], "Absent": []}
    }

    # Pattern to capture the PRESENT and ABSENT sections for Councillors
    councillor_present_pattern = r"PRESENT\s*:\s*Councillors\s*(.*?)(?=ABSENT|$)"
    councillor_absent_pattern = r"ABSENT\s*:\s*(.*?)(?=PRESENT|$)"

    # Find the present and absent sections for Councillors
    councillors_present = re.findall(councillor_present_pattern, text, re.DOTALL)
    councillors_absent = re.findall(councillor_absent_pattern, text, re.DOTALL)

    # Handle the "and" separator correctly and split names by commas and "and"
    def clean_names(names):
        # Replace "and" with a comma, and semicolons with commas
        names = names.replace(" and ", ",").replace(";", ",")
        # Split by commas and clean up spaces
        name_list = [name.strip().rstrip('.') for name in names.split(",") if name.strip()]
        return name_list

    # Apply the function to both Present and Absent sections
    sections["Councillors"]["Present"] = clean_names(councillors_present[0])
    sections["Councillors"]["Absent"] = clean_names(councillors_absent[0])

    return sections

# Helper function to extract full name (as is, no modification)
def extract_full_name(name):
    return name.strip()  # Simply return the name as is, without modification

# Helper function to extract meeting details from the header
def extract_meeting_details(text, pdf_filename):
    # Meeting Date and Day of the Week
    date_pattern = r"Meeting held on ([A-Za-z]+), (\d{4}-\d{2}-\d{2})"
    match = re.search(date_pattern, text)
    day_of_week = match.group(1) if match else ""
    meeting_date = match.group(2) if match else pdf_filename.split('-')[2]  # If not found, use the file name as fallback
    
    # Venue and City (second line below the heading)
    venue_city_pattern = r"(\S+.*?)\s+(\S+)$"  # Extracts the venue and city
    venue_city_match = re.search(venue_city_pattern, text)
    venue = venue_city_match.group(1) if venue_city_match else ""
    city = venue_city_match.group(2) if venue_city_match else ""
    
    return meeting_date, day_of_week, venue, city

# Function to split the Name column into initials and surname
def split_initials_surname(name):
    parts = name.split()
    if len(parts) == 1:  # Single-part name
        initials, surname = '', parts[0]
    elif len(parts) == 2:  # Two-part name
        initials, surname = parts[0], parts[1]
    elif len(parts) > 2:  # Multi-part name
        initials, surname = parts[0], ' '.join(parts[1:])
    else:
        initials, surname = '', ''
    return pd.Series([initials, surname])

# Path to the SQLite database
db_path = "council_data.db"

# Connect to the database and set up the table
with sqlite3.connect(db_path) as connection:
    # Drop the existing table to ensure no duplicates
    connection.execute("DROP TABLE IF EXISTS attendance_data")
    
    # Create a table to store the attendance data (including the year column)
    create_table_query = """
    CREATE TABLE IF NOT EXISTS attendance_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        attendance TEXT,
        meeting_date TEXT,
        day_of_week TEXT,
        venue TEXT,
        city TEXT,
        pdf_file TEXT,
        year TEXT
    );
    """
    connection.execute(create_table_query)

    # Define a list of (folder path, year) tuples
    pdf_directories = [
        ("C:/Users/Thandi/Documents/GitHub/my representative/myrep_attendance_analysis/council minutes/2022", "2022"),
        ("C:/Users/Thandi/Documents/GitHub/my representative/myrep_attendance_analysis/council minutes/2023", "2023"),
        ("C:/Users/Thandi/Documents/GitHub/my representative/attendance analysis/council minutes 2024", "2024")
    ]

    # Loop through each directory and process the PDF files
    for pdf_directory, year in pdf_directories:
        for pdf_file in os.listdir(pdf_directory):
            if pdf_file.endswith(".pdf"):
                pdf_path = os.path.join(pdf_directory, pdf_file)
                
                # Load the PDF and extract text
                with pdfplumber.open(pdf_path) as pdf:
                    all_text = ""
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        # Remove any header text like page numbers and specific header lines
                        page_text = re.sub(r"^\s*-?\d+\s*-?\s*", "", page_text, flags=re.MULTILINE)
                        page_text = re.sub(r"\(eThekwini Municipality.*?Council Minutes.*?\d{4}-\d{2}-\d{2}\)", "", page_text)
                        all_text += page_text

                # Extract meeting details (date, day, venue, city)
                meeting_date, day_of_week, venue, city = extract_meeting_details(all_text, pdf_file)
                
                # Extract present and absent names
                sections = extract_attendees(all_text)
                
                # Prepare data for insertion into the database, now including the year
                data = []
                for status, names in sections["Councillors"].items():
                    for name in names:
                        full_name = extract_full_name(name)
                        data.append((full_name, status, meeting_date, day_of_week, venue, city, pdf_file, year))

                # Insert the data into the database
                insert_query = """
                INSERT INTO attendance_data (name, attendance, meeting_date, day_of_week, venue, city, pdf_file, year)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """
                connection.executemany(insert_query, data)

print(f"Scraped PDF attendance data has been written to the database at {db_path}")


#%%

# Connect to the database and load the attendance data into a DataFrame
with sqlite3.connect(db_path) as connection:
    # Load attendance data into a DataFrame
    df_all_cleaned = pd.read_sql("SELECT * FROM attendance_data", connection)
    
#%%
# Initialize lists for cleaned data
all_cleaned_data = []

# Perform detailed cleaning of the data
for index, row in df_all_cleaned.iterrows():
    name = row['name']
    attendance = row['attendance']
    
    # Initialize new columns for 'role' and 'reason absent'
    df_all_cleaned.at[index, 'role'] = ''
    df_all_cleaned.at[index, 'reason absent'] = ''
    
    # Remove unwanted words
    name = name.replace("Councillors ", "").replace("AMAKHOSI", "")
    
    # Remove all occurrences of "."
    name = name.replace(".", "")
    
    # Handle text in parentheses with potential line breaks
    name = re.sub(r'\((.*?)\)', lambda m: m.group(0).replace('\n', ' '), name, flags=re.DOTALL)
    
    # If attendance is 'Present' and name has text in brackets, extract the role
    if attendance == 'Present' and '(' in name:
        role = re.search(r'\((.*?)\)', name, flags=re.DOTALL)
        if role:
            df_all_cleaned.at[index, 'role'] = role.group(1).replace('\n', ' ')  # Extract role and replace line breaks
            # Remove the text in parentheses
            name = re.sub(r'\(.*?\)', '', name, flags=re.DOTALL).strip()

    # If attendance is 'Absent' and name has text in brackets, extract the reason absent
    elif attendance == 'Absent' and '(' in name:
        reason_absent = re.search(r'\((.*?)\)', name, flags=re.DOTALL)
        if reason_absent:
            df_all_cleaned.at[index, 'reason absent'] = reason_absent.group(1).replace('\n', ' ')  # Extract reason and replace line breaks
            # Remove the text in parentheses
            name = re.sub(r'\(.*?\)', '', name, flags=re.DOTALL).strip()

    # Remove all digits from the name
    name = re.sub(r'\d', '', name)
    
    # Update the cleaned name back in the DataFrame
    df_all_cleaned.at[index, 'name'] = name.strip()
#%%
# Ensure all remaining parentheses are removed (including edge cases)
df_all_cleaned['name'] = df_all_cleaned['name'].str.replace(r'\(.*?\)', '', regex=True).str.strip()

# Split the Name column into initials and surname
df_all_cleaned[['initials', 'surname']] = df_all_cleaned['name'].apply(split_initials_surname)
### this would be a good place to try and handle the dashes###

# Convert the Attendance column to boolean
df_all_cleaned['attendance'] = df_all_cleaned['attendance'].map({'Present': True, 'Absent': False})

# Count the number of times each person was present and absent
#%%
attendance_counts = df_all_cleaned.groupby(['initials', 'surname']).agg(
    present_count=('attendance', 'sum'),
    absent_count=('attendance', lambda x: (~x).sum())  # Count False (Absent)
).reset_index()
#%%
attendance_counts = df_all_cleaned.groupby(['year', 'initials', 'surname']).agg(
    present_count=('attendance', 'sum'),
    absent_count=('attendance', lambda x: (~x).sum())  # Count False (Absent)
).reset_index()

#%%
output_file = r"C:\Users\Thandi\Documents\GitHub\my representative\myrep_attendance_analysis\complete_uncleaned_attendance_annual.xlsx"

# Use ExcelWriter to save both DataFrames to separate sheets
with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
    attendance_counts.to_excel(writer, index=False)
#%%
attendance_counts = pd.read_excel(r"C:\Users\Thandi\Documents\GitHub\my representative\myrep_attendance_analysis\complete_uncleaned_attendance_annual.xlsx")

# Sort the resulting DataFrame by the surname column alphabetically
attendance_counts = attendance_counts.sort_values(by='surname', ascending=True).reset_index(drop=True)
#%%
# Dictionary to store the meeting counts for each year
meeting_counts = {}

# Loop through each directory/year and count the PDFs
for pdf_directory, year in pdf_directories:
    count = len([f for f in os.listdir(pdf_directory) if f.endswith('.pdf')])
    meeting_counts[year] = count
    print(f"For {year}, number of meetings: {count}")

# Create individual variables for each year (defaulting to 0 if the key is missing)
num_meetings_2022 = meeting_counts.get("2022", 0)
num_meetings_2023 = meeting_counts.get("2023", 0)
num_meetings_2024 = meeting_counts.get("2024", 0)

# Calculate the total number of meetings across all years
num_meetings_total = sum(meeting_counts.values())

#%%
# Calculate attendance percentage
#num_meetings = len([f for f in os.listdir(pdf_directory) if f.endswith('.pdf')])
#num_meetings = df_all_cleaned['meeting_date'].nunique()  # Total number of unique meetings
#attendance_counts['attendance_percentage_total'] = ((attendance_counts['present_count'] / num_meetings_total) * 100).round(2)

# Map the number of meetings for each year into the DataFrame
attendance_counts['meetings_in_year'] = attendance_counts['year'].astype(str).map(meeting_counts)


attendance_counts['attendance_percentage'] = (
    (attendance_counts['present_count'] / attendance_counts['meetings_in_year']) * 100
).round(2)
#%%
'''
# Clean councillors list
df_etk_councillors = pd.read_excel(r"C:/Users/Thandi/Documents/GitHub/my representative/attendance analysis/ethekwini councillors list.xlsx")
df_etk_councillors['Surname'] = df_etk_councillors['Surname'].str.strip()
df_etk_councillors['First Name(s)'] = df_etk_councillors['First Name(s)'].str.strip()
df_etk_councillors.rename(columns={'Surname': 'last name'}, inplace=True)

# Extract initials from the First Name(s) column
df_etk_councillors['extracted_initials'] = df_etk_councillors['First Name(s)'].apply(
    lambda x: ''.join([name[0] for name in x.split() if name])
)'''
#%%

# Replace 'your_file.xlsx' with the path to your Excel file
file_path = "C:/Users/Thandi/Documents/GitHub/my representative/attendance analysis/Councillors List.xlsx"
#sheets = ["Executive Committee", "Ward Councillors", "PR Councillors"]

# Read the specified sheets into a dictionary of DataFrames
dfs = pd.read_excel(file_path)

# Access each sheet's DataFrame
#executive_committee_df = dfs["Executive Committee"]
#ward_councillors_df = dfs["Ward Councillors"]
#pr_councillors_df = dfs["PR Councillors"]
#%%
# Extract initials from the First Name(s) column
dfs['extracted_initials'] = dfs['FIRSTNAME(S)'].apply(
    lambda x: ''.join([name[0] for name in x.split() if name])
)
#%%
'''
# Extract initials from the First Name(s) column
ward_councillors_df['extracted_initials'] = ward_councillors_df['First Names'].apply(
    lambda x: ''.join([name[0] for name in x.split() if name])
)

# Extract initials from the First Name(s) column
pr_councillors_df['extracted_initials'] = pr_councillors_df['First Names'].apply(
    lambda x: ''.join([name[0] for name in x.split() if name])
)'''
#%%
# Convert the relevant columns to upper case
dfs['LASTNAME'] = dfs['LASTNAME'].str.upper()
#ward_councillors_df['Last Name'] = ward_councillors_df['Last Name'].str.upper()
#pr_councillors_df['Last Name'] = pr_councillors_df['Last Name'].str.upper()

attendance_counts['surname'] = attendance_counts['surname'].str.upper()
attendance_counts['initials'] = attendance_counts['initials'].str.upper()

#%%
# Merge attendance data with councillors list
merged_df = pd.merge(
    attendance_counts, 
    dfs, 
    left_on=['surname', 'initials'], 
    right_on=['LASTNAME', 'extracted_initials'], 
    how='left'
)

#%%
'''
# Stack the three DataFrames into one
stacked_df = pd.concat(
    [executive_committee_df, ward_councillors_df, pr_councillors_df],
    ignore_index=True
)
#%%
# Filter merged_df to only rows where "Ward No" is NaN
merged_missing = merged_df[merged_df['Ward No'].isna()].copy()

# Merge the filtered merged_df with the stacked DataFrame
merged_missing = pd.merge(
    merged_missing,
    stacked_df,
    left_on=['surname', 'initials'],
    right_on=['Last Name', 'extracted_initials'],
    how='left'
)

# Option 1: Replace the rows in merged_df where "Ward No" is NaN - this did not work the way I needed it to
#merged_df.update(merged_missing)
#%%
# Option 2: Or, if you prefer, reassemble the full DataFrame:
merged_df = pd.concat(
    [merged_df[merged_df['Ward No'].notna()], merged_missing],
    ignore_index=False
)'''

#merged_df['party'] = merged_df['Party Name'].fillna(merged_df['Political Party'])
#merged_df['First Names'] = merged_df['First Name(s)'].fillna(merged_df['First Names'])
#merged_df['Last Name'] = merged_df['last name'].fillna(merged_df['Last Name'])
#merged_df['extracted_initials'] = merged_df['extracted_initials'].fillna(merged_df['extracted_initials_y'])
#merged_df.drop(['Party Name', 'Political Party', 'last name'], axis=1, inplace=True)

#%%
'''
# Merge merged  data with PR councillor 
merged_df = pd.merge(
    merged_df, 
    pr_councillors_df, 
    left_on=['surname', 'initials'], 
    right_on=['Last Name', 'extracted_initials'], 
    how='left'
)

merged_df['party'] = merged_df['Party Name'].fillna(merged_df['Political Party'])

merged_df.drop(['Party Name', 'Political Party'], axis=1, inplace=True)


To do 25 Feb
* merge pr cuoncillor data with no extra columns
* merge ward councillor and other councillor data where there is no existing merge
may have to check for duplicates on the ethekwini list and augment that first before doing the merge '''
#%%
# Identify missing councillors
missing_councillors = merged_df[merged_df['FIRSTNAME(S)'].isna()]

# Calculate summary metrics for `results_df`
reg_count = attendance_counts.shape[0]
etk_count = dfs[['LASTNAME', 'FIRSTNAME(S)']].drop_duplicates().shape[0]
#%%


matching_councillors = pd.merge(
    attendance_counts[['surname', 'initials']], 
    dfs[['LASTNAME', 'extracted_initials']], 
    left_on=['surname', 'initials'], 
    right_on=['LASTNAME', 'extracted_initials'], 
    how='inner'
).drop_duplicates()
#%%
matching_count = matching_councillors.shape[0]
percentage_on_register = (matching_count / etk_count) * 100
#%%
# Create the results summary DataFrame
results = {
    "Metric": [
        "Total number of rows in attendance_counts",
        "Duplicated names in the register (attendance_counts)",
        "Duplicated names in the municipal list (df_etk_councillors)",
        "Total unique councillors in the municipal list",
        "Total matching councillors in the register",
        "Percentage of councillors from the municipal list on the register"
    ],
    "Value": [
        reg_count,
        attendance_counts[attendance_counts.duplicated(subset=['surname', 'initials'], keep=False)][['surname', 'initials']].to_string(index=False),
        dfs[dfs.duplicated(subset=['LASTNAME', 'FIRSTNAME(S)'], keep=False)][['LASTNAME', 'FIRSTNAME(S)']].to_string(index=False),
        etk_count,
        matching_count,
        f"{percentage_on_register:.2f}%"
    ]
}


results_df = pd.DataFrame(results)

# Save all processed data to the database
with sqlite3.connect(db_path) as connection:
    df_all_cleaned.to_sql("cleaned_data", connection, if_exists="replace", index=False)
    attendance_counts.to_sql("attendance_summary", connection, if_exists="replace", index=False)
    merged_df.to_sql("merged_data", connection, if_exists="replace", index=False)
    missing_councillors.to_sql("missing_councillors", connection, if_exists="replace", index=False)
    results_df.to_sql("summary", connection, if_exists="replace", index=False)

print(f"Data successfully saved to {db_path}")

#%%
# Example: Query and display a table
with sqlite3.connect(db_path) as connection:
    
    df = pd.read_sql("SELECT * FROM merged_data", connection)
    print(df.head())
