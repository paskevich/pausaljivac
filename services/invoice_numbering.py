def next_number(db, issue_date, fmt):
    year, month, day = (int(part) for part in issue_date.split("-"))

    row = db.execute(
        "SELECT next_seq FROM invoice_sequences WHERE year = ?", (year,)
    ).fetchone()
    if row is None:
        seq = 1
        db.execute(
            "INSERT INTO invoice_sequences (year, next_seq) VALUES (?, ?)", (year, 2)
        )
    else:
        seq = row["next_seq"]
        db.execute(
            "UPDATE invoice_sequences SET next_seq = next_seq + 1 WHERE year = ?",
            (year,),
        )
    return fmt.format(seq=seq, year=year, month=month, day=day)
