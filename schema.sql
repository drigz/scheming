drop table if exists uploaded;
create table uploaded (
    id integer primary key autoincrement,
    original_filename text not null,
    state integer not null,
    error_msg text,
    time_taken real
);
