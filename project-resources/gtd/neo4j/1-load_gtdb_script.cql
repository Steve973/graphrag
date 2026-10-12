//load Global Terrorism Database
//Copy/Paste the load script below into your Neo4j-shell command-line utility

//In order to accelerate the loading process, you want to download the CSV file from
//https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1 and then to a local file.
//After that, you would of course need to replace the URL in all of the queries below, and replace it with 
//load csv with headers from "file:/path/to/your/file.csv" as csv

//load the countries
load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with distinct toInt(csv.country) as country, csv.country_txt as country_txt
create (c:Country {id: country, name: country_txt});

create index on :Country(id);

schema await

//load the regions
load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with distinct toInt(csv.region) as region, csv.region_txt as region_txt, toInt(csv.country) as country
match (c:Country {id: country})
merge (r:Region {id: region, name: region_txt})
merge (c)-[:PART_OF]->(r);

create index on :Region(id);
create index on :ProvState(name);
schema await


//add the provinces/states
using periodic commit 2500
load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with csv.provstate as provstate, toInt(csv.country) as country
where provstate is not null
match (c:Country {id: country})
merge (ps:ProvState {name: provstate})-[:PART_OF]->(c);

using periodic commit 2500
load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with csv.provstate as provstate, toInt(csv.country) as country
where provstate is null
match (c:Country {id: country})
merge (ps:ProvState {name: "Unknown Province/State"})-[:PART_OF]->(c);


//add the cities
//with province/states
create index on :City(name);

schema await

using periodic commit 2500
load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with csv.provstate as provstate, toInt(csv.country) as country, csv.city as city
where provstate is not null
match (ps:ProvState {name: provstate})-[:PART_OF]->(c:Country {id: country})
merge (ci:City {name: city})-[:PART_OF]->(ps);

//add the cities
//without province/state
using periodic commit 2500
load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with csv.provstate as provstate, toInt(csv.country) as country, csv.city as city
where provstate is null
match (ps:ProvState {name: "Unknown Province/State"})-[:PART_OF]->(c:Country {id: country})
merge (ci:City {name: city})-[:PART_OF]->(ps);

//add the Attacktype
create index on :AttackType(id);

schema await

using periodic commit 2500
load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with distinct toInt(csv.attacktype1) as attacktype, csv.attacktype1_txt as attacktype_txt
where attacktype is not null
merge (at:AttackType {id: attacktype, name: attacktype_txt});

using periodic commit 2500
load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with distinct toInt(csv.attacktype2) as attacktype, csv.attacktype2_txt as attacktype_txt
where attacktype is not null
merge (at:AttackType {id: attacktype, name: attacktype_txt});

using periodic commit 2500
load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with distinct toInt(csv.attacktype3) as attacktype, csv.attacktype3_txt as attacktype_txt
where attacktype is not null
merge (at:AttackType {id: attacktype, name: attacktype_txt});

//add the TargetType
create index on :TargetType(id);
schema await

create index on :TargetType(name);
schema await

load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with distinct toInt(csv.targtype1) as targtype, csv.targtype1_txt as targtype_txt
where targtype is not null
merge (at:TargetType {id: targtype, name: targtype_txt});

load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with distinct toInt(csv.targtype2) as targtype, csv.targtype2_txt as targtype_txt
where targtype is not null
merge (at:TargetType {id: targtype, name: targtype_txt});

load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with distinct toInt(csv.targtype3) as targtype, csv.targtype3_txt as targtype_txt
where targtype is not null
merge (at:TargetType {id: targtype, name: targtype_txt});

//create Targets
create index on :Target(name);
schema await

using periodic commit 2500
load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with distinct csv.target1 as target
where target is not null
merge (t:Target {name: target});

using periodic commit 2500
load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with distinct csv.target2 as target
where target is not null
merge (t:Target {name: target});

using periodic commit 2500
load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with distinct csv.target3 as target
where target is not null
merge (t:Target {name: target});

//connect targets to targettypes
using periodic commit 2500
load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with distinct csv.target1 as target, toInt(csv.targtype1) as targtype
where target is not null
match (tt:TargetType {id: targtype}), (t:Target {name: target})
merge (t)-[:IS_A]->(tt);

using periodic commit 2500
load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with distinct csv.target2 as target, toInt(csv.targtype2) as targtype
where target is not null
match (tt:TargetType {id: targtype}), (t:Target {name: target})
merge (t)-[:IS_A]->(tt);

using periodic commit 2500
load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with distinct csv.target3 as target, toInt(csv.targtype3) as targtype
where target is not null
match (tt:TargetType {id: targtype}), (t:Target {name: target})
merge (t)-[:IS_A]->(tt);

//create Corporations
create index on :Corporation(name);
schema await

load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with distinct csv.corp1 as corporation
where corporation is not null
merge (c:Corporation {name: corporation});

load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with distinct csv.corp2 as corporation
where corporation is not null
merge (c:Corporation {name: corporation});

load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with distinct csv.corp3 as corporation
where corporation is not null
merge (c:Corporation {name: corporation});

//link the corporations to the targets
load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with distinct csv.corp1 as corporation, csv.target1 as target
where corporation is not null and target is not null
match (t:Target {name: target}), (c:Corporation {name: corporation})
merge (c)-[:RELATED_TO]->(t);

load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with distinct csv.corp2 as corporation, csv.target2 as target
where corporation is not null and target is not null
match (t:Target {name: target}), (c:Corporation {name: corporation})
merge (c)-[:RELATED_TO]->(t);

load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with distinct csv.corp3 as corporation, csv.target3 as target
where corporation is not null and target is not null
match (t:Target {name: target}), (c:Corporation {name: corporation})
merge (c)-[:RELATED_TO]->(t);

//link targets to countries
load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with distinct toInt(csv.natlty1) as nationality, csv.target1 as target
where nationality is not null and target is not null
match (c:Country {id: nationality}), (t:Target {name: target})
merge (t)-[:IS_FROM]->(c);

load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with distinct toInt(csv.natlty2) as nationality, csv.target2 as target
where nationality is not null and target is not null
match (c:Country {id: nationality}), (t:Target {name: target})
merge (t)-[:IS_FROM]->(c);

load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with distinct toInt(csv.natlty3) as nationality, csv.target3 as target
where nationality is not null and target is not null
match (c:Country {id: nationality}), (t:Target {name: target})
merge (t)-[:IS_FROM]->(c);

//load the groups
create index on :Group(name);
schema await

load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with distinct csv.gname as group
where group is not null
merge (g:Group {name: group});

load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with distinct csv.gname2 as group
where group is not null
merge (g:Group {name: group});

load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with distinct csv.gname3 as group
where group is not null
merge (g:Group {name: group});


//load the weapontypes
create index on :Weapon(id);
schema await

create index on :Weapon(name);
schema await

load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with distinct toInt(csv.weaptype1) as weapontype, csv.weaptype1_txt as weapontype_txt
where weapontype is not null
merge (w:Weapon {id: weapontype, name: weapontype_txt});

load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with distinct toInt(csv.weaptype2) as weapontype, csv.weaptype2_txt as weapontype_txt
where weapontype is not null
merge (w:Weapon {id: weapontype, name: weapontype_txt});

load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with distinct toInt(csv.weaptype3) as weapontype, csv.weaptype3_txt as weapontype_txt
where weapontype is not null
merge (w:Weapon {id: weapontype, name: weapontype_txt});

load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with distinct toInt(csv.weaptype4) as weapontype, csv.weaptype4_txt as weapontype_txt
where weapontype is not null
merge (w:Weapon {id: weapontype, name: weapontype_txt});


//load the events

create index on :Event(id);
schema await

using periodic commit
load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
create (e:Event {id: toInt(csv.eventid), year: toInt(csv.iyear), month: toInt(csv.imonth), day: toInt(csv.iday) , latitude: csv.latitude, longitude: csv.longitude, specificity: csv.specificity, vicinity: csv.vicinity, location: csv.location, summary: csv.summary, crit1: toint(csv.crit1), crit2: toInt(csv.crit2), crit3: toInt(csv.crit3), doubt: toInt(csv.doubtterr), alternative: csv.alternative_txt, multiple: toInt(csv.multiple), success: toInt(csv.success), suicide: toInt(csv.suicide), motive: csv.motive, weapondetail: csv.weapdetail, nkill: csv.nkill, nkillter: csv.nkillter, nwound: csv.nwound, nwoundter: csv.nwoundte, property: csv.property, propextent: csv.propextent, propextent_txt: csv.propextent_txt, propvalue: csv.propvalue, propcomment: csv.propcomment, ransom: toInt(csv.ransom), ransomamt: toInt(csv.ransomamt), ransomnote: csv.ransomnote, addnotes: csv.addnotes, dbsource: csv.dbsource});


//connect events to cities
using periodic commit
load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with toInt(csv.eventid) as event, csv.city as city, toInt(csv.country) as country, toInt(csv.region) as region, csv.provstate as provstate
where city is not null and provstate is not null
match p = ((ci:City {name: city})-->(ps:ProvState {name: provstate})-->(co:Country {id: country})-->(r:Region {id: region}))
with ci, event
match (e:Event {id: event})
create (e)-[:EVENT_LOCATED_IN]->(ci);

//connect event to attachtypes
using periodic commit
load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with toInt(csv.eventid) as event, toInt(csv.attacktype1) as attacktype
where attacktype is not null
match (e:Event {id: event}), (at:AttackType {id: attacktype})
create (e)-[:IS_OF_ATTACKTYPE]->(at);

load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with toInt(csv.eventid) as event, toInt(csv.attacktype2) as attacktype
where attacktype is not null
match (e:Event {id: event}), (at:AttackType {id: attacktype})
create (e)-[:IS_OF_ATTACKTYPE]->(at);

load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with toInt(csv.eventid) as event, toInt(csv.attacktype3) as attacktype
where attacktype is not null
match (e:Event {id: event}), (at:AttackType {id: attacktype})
create (e)-[:IS_OF_ATTACKTYPE]->(at);

load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with toInt(csv.eventid) as event, toInt(csv.attacktype4) as attacktype
where attacktype is not null
match (e:Event {id: event}), (at:AttackType {id: attacktype})
create (e)-[:IS_OF_ATTACKTYPE]->(at);

//connect events to targets
load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with toInt(csv.eventid) as event, csv.target1 as target
where target is not null
match (e:Event {id: event}), (t:Target {name: target})
create (e)-[:TARGETS]->(t);

load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with toInt(csv.eventid) as event, csv.target2 as target
where target is not null
match (e:Event {id: event}), (t:Target {name: target})
create (e)-[:TARGETS]->(t);

load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with toInt(csv.eventid) as event, csv.target3 as target
where target is not null
match (e:Event {id: event}), (t:Target {name: target})
create (e)-[:TARGETS]->(t);

//connect the groups to the events
load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with toInt(csv.eventid) as event, csv.gname as group
where group is not null
match (e:Event {id: event}), (g:Group {name: group})
create (e)<-[:CARRIES_OUT]-(g);

load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with toInt(csv.eventid) as event, csv.gname2 as group
where group is not null
match (e:Event {id: event}), (g:Group {name: group})
create (e)<-[:CARRIES_OUT]-(g);

load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with toInt(csv.eventid) as event, csv.gname3 as group
where group is not null
match (e:Event {id: event}), (g:Group {name: group})
create (e)<-[:CARRIES_OUT]-(g);

//Link events to weapontypes
load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with toInt(csv.eventid) as event, toInt(csv.weaptype1) as weapon
where weapon is not null
match (e:Event {id: event}), (w:Weapon {id: weapon})
create (e)-[:USED_WEAPON]->(w);

load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with toInt(csv.eventid) as event, toInt(csv.weaptype2) as weapon
where weapon is not null
match (e:Event {id: event}), (w:Weapon {id: weapon})
create (e)-[:USED_WEAPON]->(w);

load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with toInt(csv.eventid) as event, toInt(csv.weaptype3) as weapon
where weapon is not null
match (e:Event {id: event}), (w:Weapon {id: weapon})
create (e)-[:USED_WEAPON]->(w);

load csv with headers from "https://www.dropbox.com/s/oequ58lrp8f9w6v/gtdb_transform.csv?dl=1
" as csv
fieldterminator ';'
with toInt(csv.eventid) as event, toInt(csv.weaptype4) as weapon
where weapon is not null
match (e:Event {id: event}), (w:Weapon {id: weapon})
create (e)-[:USED_WEAPON]->(w);

match (n) return count(n);
match ()-[r]->() return count(r);
