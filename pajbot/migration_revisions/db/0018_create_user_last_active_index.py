def up(cursor, bot):
    # for the mass points module check, it uses a check like this:
    # UPDATE "user"
    # SET points = points + $1
    # WHERE "user".last_active >= $2
    # So this query becomes much faster with an index on last_active.
    cursor.execute('CREATE INDEX ON "user"(last_active)')
