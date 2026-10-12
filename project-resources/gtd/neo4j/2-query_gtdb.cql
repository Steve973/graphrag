//the Meta graph
MATCH (n:Meta_Node) RETURN n LIMIT 25

//Find Belgium
match (c:Country {name:"Belgium"})
return c;

match (c:Country {name:"Belgium"})-[r]-()
return c,r
limit 10;

//find Antwerp
match (c:City {name:"Antwerp"})-[r]-()
return c,r;

//find the events in Belgium
match (e:Event)-->(ci:City)-->(ps:ProvState)-->(c:Country {name:"Belgium"})
return c.name, e.id;

//Nr of events per Country
match p=(e:Event)-->(ci:City)-->(ps:ProvState)-->(co:Country)
return distinct co.name as Country, count(e) as NRofEvents
order by NRofEvents DESC

//Nr of Groups per country
match p=(g:Group)-->(e:Event)-->(ci:City)-->(ps:ProvState)-->(co:Country)
return distinct co.name as Country, count(g) as NRofGroups
order by NRofGroups DESC

//Nr of attacks per group per Country
match p=(g:Group)-->(e:Event)-->(ci:City)-->(ps:ProvState)-->(co:Country)
return g.name, co.name, count(e)
order by count(e) DESC

//find the active groups associated with Belgium
match (g:Group), (c:Country {name: "Belgium"}),
p = allshortestpaths((g)-[*]-(c))
return p
limit 10;

//find the attacktypes in Belgium
match (at:AttackType {id:4}), (c:Country {name:"Belgium"}),
p = allshortestpaths((at)-[*]-(c))
return p
limit 10;

//linking attacktypes to targettypes?
match p=(a:AttackType)<--(e:Event)-->(t:Target)-->(tt:TargetType)
return a.name, tt.name, count(e)
order by a.name ASC, tt.name ASC


//find the Oklahoma City bombing
match (c:City {name:"Oklahoma City"}) return c;
match (e:Event {id: 199504190004}) return e

//find 9/11
match (e:Event)
where left(str(e.id),8)="20010911"
return e

//find the links between 2 events
match (e1:Event {id: 199504190004}), (e2:Event)
where left(str(e2.id),8)="20010911"
with e1,e2
match p = allshortestpaths ( (e1)-[*]-(e2) )
return p
limit 10


//find the links between two specific events
match (e2:Event)
using scan e2:Event
where left(str(e2.id),8)="20010911"
with e2 as Event
match p = allshortestpaths ((Event)-[*..3]-(c:Country {name:"United States"}))
With Event
match p2 = allshortestpaths((e1:Event {id: 199504190004})-[*]-(Event))
return p2
limit 10;
