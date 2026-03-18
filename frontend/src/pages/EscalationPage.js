import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { ScrollArea } from '../components/ui/scroll-area';
import { toast } from 'sonner';
import axios from 'axios';
import {
  AlertTriangle,
  Plus,
  Mail,
  Clock,
  Users,
  RefreshCw,
  Trash2,
  Send,
  Loader2,
  CheckCircle
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const PriorityBadge = ({ priority }) => {
  const styles = {
    P1: 'bg-red-600 text-white',
    P2: 'bg-orange-500 text-white',
  };
  return <Badge className={`${styles[priority] || 'bg-slate-500'}`}>{priority}</Badge>;
};

const LevelBadge = ({ level }) => {
  const styles = {
    1: 'bg-amber-50 text-amber-700 border-amber-200',
    2: 'bg-orange-50 text-orange-700 border-orange-200',
    3: 'bg-red-50 text-red-700 border-red-200',
  };
  const names = {
    1: 'Team Lead',
    2: 'Service Delivery Manager',
    3: 'Director',
  };
  return (
    <Badge variant="outline" className={styles[level]}>
      L{level} - {names[level]}
    </Badge>
  );
};

export default function EscalationPage() {
  const [contacts, setContacts] = useState([]);
  const [levels, setLevels] = useState([]);
  const [escalationsNeeded, setEscalationsNeeded] = useState([]);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [sending, setSending] = useState({});
  const [isAddOpen, setIsAddOpen] = useState(false);
  
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    role: 'team_lead',
    level: 1
  });

  const fetchData = async () => {
    try {
      const [contactsRes, levelsRes] = await Promise.all([
        axios.get(`${API}/escalation/contacts`),
        axios.get(`${API}/escalation/levels`)
      ]);
      setContacts(contactsRes.data);
      setLevels(levelsRes.data);
    } catch (error) {
      toast.error('Failed to fetch data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCheckEscalations = async () => {
    setChecking(true);
    try {
      const response = await axios.post(`${API}/escalation/check`);
      setEscalationsNeeded(response.data.escalations_needed);
      if (response.data.count === 0) {
        toast.success('No escalations needed at this time');
      } else {
        toast.warning(`${response.data.count} escalations need attention`);
      }
    } catch (error) {
      toast.error('Failed to check escalations');
    } finally {
      setChecking(false);
    }
  };

  const handleAddContact = async () => {
    try {
      await axios.post(`${API}/escalation/contacts`, formData);
      toast.success('Contact added');
      setIsAddOpen(false);
      setFormData({ name: '', email: '', role: 'team_lead', level: 1 });
      fetchData();
    } catch (error) {
      toast.error('Failed to add contact');
    }
  };

  const handleDeleteContact = async (contactId) => {
    if (!window.confirm('Are you sure you want to delete this contact?')) return;
    try {
      await axios.delete(`${API}/escalation/contacts/${contactId}`);
      toast.success('Contact deleted');
      fetchData();
    } catch (error) {
      toast.error('Failed to delete contact');
    }
  };

  const handleSendEscalation = async (incidentId, level) => {
    setSending(prev => ({ ...prev, [`${incidentId}-${level}`]: true }));
    try {
      const response = await axios.post(`${API}/escalation/send?incident_id=${incidentId}&level=${level}`);
      toast.success(`Escalation sent to ${response.data.level}`);
      handleCheckEscalations();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to send escalation');
    } finally {
      setSending(prev => ({ ...prev, [`${incidentId}-${level}`]: false }));
    }
  };

  const roleOptions = [
    { value: 'team_lead', label: 'Team Lead', level: 1 },
    { value: 'sdm', label: 'Service Delivery Manager', level: 2 },
    { value: 'director', label: 'Director', level: 3 },
  ];

  return (
    <div data-testid="escalation-page" className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight font-['Manrope']">Escalation Management</h1>
          <p className="text-muted-foreground mt-1">Configure escalation contacts and monitor overdue incidents</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleCheckEscalations} disabled={checking}>
            {checking ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Checking...
              </>
            ) : (
              <>
                <RefreshCw className="h-4 w-4 mr-2" />
                Check Escalations
              </>
            )}
          </Button>
          <Dialog open={isAddOpen} onOpenChange={setIsAddOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Add Contact
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Add Escalation Contact</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label>Name</Label>
                  <Input
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="John Smith"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Email</Label>
                  <Input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    placeholder="john.smith@company.com"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Role / Escalation Level</Label>
                  <Select 
                    value={formData.role} 
                    onValueChange={(v) => {
                      const role = roleOptions.find(r => r.value === v);
                      setFormData({ ...formData, role: v, level: role?.level || 1 });
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {roleOptions.map(role => (
                        <SelectItem key={role.value} value={role.value}>
                          L{role.level} - {role.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setIsAddOpen(false)}>Cancel</Button>
                <Button onClick={handleAddContact}>Add Contact</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Escalation Levels Info */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {levels.map(level => (
          <Card key={level.level} className="bg-white border-border/50">
            <CardContent className="p-4">
              <div className="flex items-start justify-between">
                <div>
                  <LevelBadge level={level.level} />
                  <p className="mt-2 text-sm text-muted-foreground">
                    Triggered after <strong>{level.threshold_hours} hours</strong>
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    For: {level.priority_filter.join(', ')} incidents
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-2xl font-bold">
                    {contacts.filter(c => c.level === level.level).length}
                  </p>
                  <p className="text-xs text-muted-foreground">contacts</p>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Pending Escalations */}
      {escalationsNeeded.length > 0 && (
        <Card className="bg-red-50 border-red-200">
          <CardHeader>
            <CardTitle className="text-lg font-semibold text-red-700 flex items-center gap-2">
              <AlertTriangle className="h-5 w-5" />
              Pending Escalations ({escalationsNeeded.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {escalationsNeeded.map((esc, index) => (
                <div key={index} className="flex items-center justify-between p-3 bg-white rounded-lg border border-red-200">
                  <div>
                    <div className="flex items-center gap-2">
                      <PriorityBadge priority={esc.incident.priority} />
                      <span className="font-medium">{esc.incident.title}</span>
                    </div>
                    <p className="text-sm text-muted-foreground mt-1">
                      Open for {esc.hours_open} hours • Needs {esc.level.name} escalation
                    </p>
                  </div>
                  <Button
                    onClick={() => handleSendEscalation(esc.incident.id, esc.level.level)}
                    disabled={sending[`${esc.incident.id}-${esc.level.level}`]}
                    className="bg-red-600 hover:bg-red-700"
                  >
                    {sending[`${esc.incident.id}-${esc.level.level}`] ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4 mr-2" />
                    )}
                    Escalate
                  </Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Contacts Table */}
      <Card className="bg-white border-border/50">
        <CardHeader>
          <CardTitle className="text-lg font-semibold flex items-center gap-2">
            <Users className="h-5 w-5" />
            Escalation Contacts
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <ScrollArea className="h-[400px]">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Level</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-10">
                      <RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
                    </TableCell>
                  </TableRow>
                ) : contacts.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-10 text-muted-foreground">
                      No escalation contacts configured. Add contacts for each level.
                    </TableCell>
                  </TableRow>
                ) : (
                  contacts.map((contact) => (
                    <TableRow key={contact.id}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Mail className="h-4 w-4 text-muted-foreground" />
                          <span className="font-medium">{contact.name}</span>
                        </div>
                      </TableCell>
                      <TableCell>{contact.email}</TableCell>
                      <TableCell className="capitalize">{contact.role.replace('_', ' ')}</TableCell>
                      <TableCell><LevelBadge level={contact.level} /></TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDeleteContact(contact.id)}
                          className="text-red-600 hover:text-red-700"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </ScrollArea>
        </CardContent>
      </Card>

      {/* Escalation Timeline Info */}
      <Card className="bg-white border-border/50">
        <CardHeader>
          <CardTitle className="text-lg font-semibold flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Escalation Timeline
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="relative pl-8">
            <div className="absolute left-3 top-0 bottom-0 w-0.5 bg-border" />
            
            <div className="relative pb-8">
              <div className="absolute left-[-22px] w-4 h-4 rounded-full bg-amber-500" />
              <div className="ml-4">
                <p className="font-medium">Level 1 - Team Lead</p>
                <p className="text-sm text-muted-foreground">
                  After 4 hours of P1/P2 incident without response
                </p>
              </div>
            </div>
            
            <div className="relative pb-8">
              <div className="absolute left-[-22px] w-4 h-4 rounded-full bg-orange-500" />
              <div className="ml-4">
                <p className="font-medium">Level 2 - Service Delivery Manager</p>
                <p className="text-sm text-muted-foreground">
                  After 8 hours of P1/P2 incident without response
                </p>
              </div>
            </div>
            
            <div className="relative">
              <div className="absolute left-[-22px] w-4 h-4 rounded-full bg-red-500" />
              <div className="ml-4">
                <p className="font-medium">Level 3 - Director</p>
                <p className="text-sm text-muted-foreground">
                  After 12 hours of P1 incident without response
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
