# The idea is that we have two stages: 1) compilation of the database and 2) interaction/interface to the db
# 1) can be treated as optional dependencies, for shipping, very minimal requirements are needed
# the user should not have to worry about 1) when they just want to use the library.
# The database can be read-only in the interface step!
