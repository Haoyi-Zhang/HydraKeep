// Authored closed transition subset. These are the actual browser handlers.
// No inferred effect changes the independent ownership contract.
window.HANDLERS={
  independent_a:(s,v)=>{s.a=v;},
  independent_b:(s,v)=>{s.b=v;},
  coupled_a:(s,v)=>{s.a=v;s.b='seed-b';},
  coupled_b:(s,v)=>{s.b=v;},
  hidden_a:(s,v)=>{s.a=v;s.b='seed-b';},
  hidden_b:(s,v)=>{s.b=v;}
};
