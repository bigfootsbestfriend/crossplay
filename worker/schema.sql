-- One vote per player (hashed IP) per game; voting again replaces the earlier vote.
CREATE TABLE IF NOT EXISTS votes (
  slug TEXT NOT NULL,
  who TEXT NOT NULL,
  result TEXT NOT NULL CHECK (result IN ('yes', 'no')),
  a TEXT, b TEXT,
  created INTEGER NOT NULL,
  PRIMARY KEY (slug, who)
);

-- Tips/reviews and "this page is wrong" reports. Nothing is shown until status = 'approved'.
CREATE TABLE IF NOT EXISTS posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL CHECK (kind IN ('review', 'report')),
  slug TEXT NOT NULL,
  name TEXT, platform TEXT,
  body TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'done')),
  who TEXT NOT NULL,
  created INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS posts_slug ON posts (slug, status);
CREATE INDEX IF NOT EXISTS posts_status ON posts (status, created);
