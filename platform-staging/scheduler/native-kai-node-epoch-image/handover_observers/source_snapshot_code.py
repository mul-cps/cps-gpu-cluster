import json,sqlite3,sys
v=json.load(sys.stdin)
db=sqlite3.connect('file:/data/courses.sqlite?mode=ro',uri=True)
db.execute('PRAGMA query_only=ON');db.execute('BEGIN')
rows=db.execute('SELECT id,payload FROM records WHERE console=? AND kind=? AND id=?',(v['source'],'workspaces',v['workspace'])).fetchall()
assert len(rows)==1
w=json.loads(rows[0][1])
sql="SELECT payload FROM records WHERE console=? AND kind=? AND json_extract(payload,'$.course_id')=? AND json_extract(payload,'$.group_id')=?"
siblings=[json.loads(x[0]) for x in db.execute(sql,(v['source'],'workspaces',w['course_id'],w['group_id']))]
print(json.dumps({'source':v['source'],'workspace':w,'same_group_writers':siblings}))
db.rollback();db.close()
