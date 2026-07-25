"""Fixed quiz answers for sample_data/messy_resume_example.txt, shared by the model
comparison script and the cached-fallback generator so both stay in sync."""

SAMPLE_ANSWERS = {
    "\"Team Member\" is a general title. What was your actual job title?":
        "Customer Service Representative",
    "\"Sales Associate\" is a general title. What was your actual job title?":
        "Retail Sales Associate",
    "What were the start and end dates for \"Marketing Intern\"?":
        "Jun 2022 - Aug 2022",
    "Can you quantify the result for \"Helped customers with their orders\"? "
    "(a number, percentage, or measurable outcome)":
        "Assisted an average of 50 customers per day",
    "Can you quantify the result for \"Worked on team projects\"? "
    "(a number, percentage, or measurable outcome)":
        "Contributed to a team project that increased store sales by 10%",
}
