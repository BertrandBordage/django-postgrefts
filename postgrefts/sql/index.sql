CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS btree_gin;

CREATE TEXT SEARCH CONFIGURATION fr ( COPY = french );
CREATE TEXT SEARCH DICTIONARY fr_stop (
   TEMPLATE = simple,
   StopWords = 'french', Accept = false
);
-- myspell-fr must be installed in order to get this dict working.
CREATE TEXT SEARCH DICTIONARY fr_ispell (
   TEMPLATE = ispell,
   DictFile = 'fr', AffFile = 'fr'
);
CREATE TEXT SEARCH DICTIONARY fr_stem (
   TEMPLATE = snowball,
   Language = 'french'
);
ALTER TEXT SEARCH CONFIGURATION fr
    ALTER MAPPING FOR asciihword, asciiword WITH fr_stop, fr_ispell, simple;
ALTER TEXT SEARCH CONFIGURATION fr
    ALTER MAPPING FOR hword, hword_asciipart, hword_part, word WITH fr_stop, fr_ispell, unaccent, simple;

CREATE INDEX content_type_id_title_search ON postgrefts_index USING gin(content_type_id, title_search);
CREATE INDEX title_search ON postgrefts_index USING gin(title_search);
CREATE INDEX body_search ON postgrefts_index USING gin(body_search);
