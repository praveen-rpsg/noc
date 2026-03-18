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
import { assetsApi } from '../services/api';
import { toast } from 'sonner';
import {
  Package,
  Plus,
  Search,
  RefreshCw,
  Pencil,
  Trash2,
  AlertTriangle,
  Calendar,
  MapPin,
  User
} from 'lucide-react';
import { format, differenceInDays, parseISO } from 'date-fns';

const StatusBadge = ({ status }) => {
  const styles = {
    active: 'bg-green-50 text-green-700 border-green-200',
    inactive: 'bg-slate-50 text-slate-700 border-slate-200',
    maintenance: 'bg-blue-50 text-blue-700 border-blue-200',
    retired: 'bg-red-50 text-red-700 border-red-200',
  };

  return (
    <Badge variant="outline" className={`${styles[status] || styles.active} capitalize`}>
      {status}
    </Badge>
  );
};

const WarrantyBadge = ({ expiryDate }) => {
  if (!expiryDate) return null;
  
  const daysUntilExpiry = differenceInDays(parseISO(expiryDate), new Date());
  
  if (daysUntilExpiry < 0) {
    return <Badge variant="destructive">Expired</Badge>;
  } else if (daysUntilExpiry < 30) {
    return <Badge className="bg-amber-500">Expiring Soon</Badge>;
  } else if (daysUntilExpiry < 90) {
    return <Badge className="bg-blue-500">{daysUntilExpiry} days left</Badge>;
  }
  return <Badge className="bg-green-500">Valid</Badge>;
};

const initialFormState = {
  name: '',
  asset_tag: '',
  type: 'Network',
  vendor: '',
  model: '',
  serial_number: '',
  location: '',
  owner: '',
  purchase_date: '',
  warranty_expiry: '',
  eol_date: '',
  contract_details: '',
  license_info: '',
};

export default function AssetsPage() {
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState('all');
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [selectedAsset, setSelectedAsset] = useState(null);
  const [formData, setFormData] = useState(initialFormState);

  const fetchAssets = async () => {
    try {
      const response = await assetsApi.getAll();
      setAssets(response.data);
    } catch (error) {
      toast.error('Failed to fetch assets');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAssets();
  }, []);

  const filteredAssets = assets.filter((asset) => {
    const matchesSearch = asset.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      asset.asset_tag.toLowerCase().includes(searchQuery.toLowerCase()) ||
      asset.serial_number.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesType = filterType === 'all' || asset.type === filterType;
    return matchesSearch && matchesType;
  });

  const handleCreate = async () => {
    try {
      await assetsApi.create(formData);
      toast.success('Asset created successfully');
      setIsCreateOpen(false);
      setFormData(initialFormState);
      fetchAssets();
    } catch (error) {
      toast.error('Failed to create asset');
    }
  };

  const handleEdit = async () => {
    try {
      await assetsApi.update(selectedAsset.id, formData);
      toast.success('Asset updated successfully');
      setIsEditOpen(false);
      setSelectedAsset(null);
      fetchAssets();
    } catch (error) {
      toast.error('Failed to update asset');
    }
  };

  const handleDelete = async (asset) => {
    if (window.confirm(`Are you sure you want to delete ${asset.name}?`)) {
      try {
        await assetsApi.delete(asset.id);
        toast.success('Asset deleted successfully');
        fetchAssets();
      } catch (error) {
        toast.error('Failed to delete asset');
      }
    }
  };

  const openEditDialog = (asset) => {
    setSelectedAsset(asset);
    setFormData({
      name: asset.name,
      asset_tag: asset.asset_tag,
      type: asset.type,
      vendor: asset.vendor,
      model: asset.model,
      serial_number: asset.serial_number,
      location: asset.location,
      owner: asset.owner,
      purchase_date: asset.purchase_date || '',
      warranty_expiry: asset.warranty_expiry || '',
      eol_date: asset.eol_date || '',
      contract_details: asset.contract_details || '',
      license_info: asset.license_info || '',
    });
    setIsEditOpen(true);
  };

  const assetStats = {
    total: assets.length,
    active: assets.filter(a => a.status === 'active').length,
    expiringWarranty: assets.filter(a => {
      if (!a.warranty_expiry) return false;
      const days = differenceInDays(parseISO(a.warranty_expiry), new Date());
      return days > 0 && days < 90;
    }).length,
    eolApproaching: assets.filter(a => {
      if (!a.eol_date) return false;
      const days = differenceInDays(parseISO(a.eol_date), new Date());
      return days > 0 && days < 180;
    }).length,
  };

  return (
    <div data-testid="assets-page" className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight font-['Manrope']">Asset Management</h1>
          <p className="text-muted-foreground mt-1">Track and manage IT assets and inventory</p>
        </div>
        <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
          <DialogTrigger asChild>
            <Button data-testid="add-asset-btn">
              <Plus className="h-4 w-4 mr-2" />
              Add Asset
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[600px]">
            <DialogHeader>
              <DialogTitle>Add New Asset</DialogTitle>
            </DialogHeader>
            <div className="grid gap-4 py-4 max-h-[60vh] overflow-y-auto">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Asset Name</Label>
                  <Input
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="Core Router"
                    data-testid="asset-name-input"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Asset Tag</Label>
                  <Input
                    value={formData.asset_tag}
                    onChange={(e) => setFormData({ ...formData, asset_tag: e.target.value })}
                    placeholder="NET-001"
                    data-testid="asset-tag-input"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Type</Label>
                  <Select value={formData.type} onValueChange={(v) => setFormData({ ...formData, type: v })}>
                    <SelectTrigger data-testid="asset-type-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Network">Network</SelectItem>
                      <SelectItem value="Server">Server</SelectItem>
                      <SelectItem value="Storage">Storage</SelectItem>
                      <SelectItem value="Security">Security</SelectItem>
                      <SelectItem value="Software">Software</SelectItem>
                      <SelectItem value="Other">Other</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Location</Label>
                  <Input
                    value={formData.location}
                    onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                    placeholder="DC-East"
                    data-testid="asset-location-input"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Vendor</Label>
                  <Input
                    value={formData.vendor}
                    onChange={(e) => setFormData({ ...formData, vendor: e.target.value })}
                    placeholder="Cisco"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Model</Label>
                  <Input
                    value={formData.model}
                    onChange={(e) => setFormData({ ...formData, model: e.target.value })}
                    placeholder="ASR 9000"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Serial Number</Label>
                  <Input
                    value={formData.serial_number}
                    onChange={(e) => setFormData({ ...formData, serial_number: e.target.value })}
                    placeholder="SN123456"
                    data-testid="asset-serial-input"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Owner</Label>
                  <Input
                    value={formData.owner}
                    onChange={(e) => setFormData({ ...formData, owner: e.target.value })}
                    placeholder="Network Team"
                    data-testid="asset-owner-input"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Warranty Expiry</Label>
                  <Input
                    type="date"
                    value={formData.warranty_expiry}
                    onChange={(e) => setFormData({ ...formData, warranty_expiry: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>EOL Date</Label>
                  <Input
                    type="date"
                    value={formData.eol_date}
                    onChange={(e) => setFormData({ ...formData, eol_date: e.target.value })}
                  />
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setIsCreateOpen(false)}>Cancel</Button>
              <Button onClick={handleCreate} data-testid="save-asset-btn">Save Asset</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-xl bg-blue-50">
              <Package className="h-6 w-6 text-blue-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{assetStats.total}</p>
              <p className="text-sm text-muted-foreground">Total Assets</p>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-xl bg-green-50">
              <Package className="h-6 w-6 text-green-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-green-600">{assetStats.active}</p>
              <p className="text-sm text-muted-foreground">Active</p>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-xl bg-amber-50">
              <Calendar className="h-6 w-6 text-amber-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-amber-600">{assetStats.expiringWarranty}</p>
              <p className="text-sm text-muted-foreground">Warranty Expiring</p>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-xl bg-red-50">
              <AlertTriangle className="h-6 w-6 text-red-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-red-600">{assetStats.eolApproaching}</p>
              <p className="text-sm text-muted-foreground">EOL Approaching</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card className="bg-white border-border/50">
        <CardContent className="p-4">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search by name, tag, or serial..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
                data-testid="asset-search"
              />
            </div>
            <Select value={filterType} onValueChange={setFilterType}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                <SelectItem value="Network">Network</SelectItem>
                <SelectItem value="Server">Server</SelectItem>
                <SelectItem value="Storage">Storage</SelectItem>
                <SelectItem value="Security">Security</SelectItem>
                <SelectItem value="Software">Software</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" onClick={fetchAssets}>
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Assets Table */}
      <Card className="bg-white border-border/50">
        <CardContent className="p-0">
          <ScrollArea className="h-[500px]">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Asset</TableHead>
                  <TableHead>Tag</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Location</TableHead>
                  <TableHead>Owner</TableHead>
                  <TableHead>Warranty</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={8} className="text-center py-10">
                      <RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
                    </TableCell>
                  </TableRow>
                ) : filteredAssets.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} className="text-center py-10 text-muted-foreground">
                      No assets found
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredAssets.map((asset) => (
                    <TableRow key={asset.id} className="table-row-hover" data-testid={`asset-row-${asset.id}`}>
                      <TableCell>
                        <div>
                          <p className="font-medium">{asset.name}</p>
                          <p className="text-xs text-muted-foreground">{asset.vendor} {asset.model}</p>
                        </div>
                      </TableCell>
                      <TableCell className="font-mono text-sm">{asset.asset_tag}</TableCell>
                      <TableCell>{asset.type}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <MapPin className="h-3 w-3 text-muted-foreground" />
                          {asset.location}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <User className="h-3 w-3 text-muted-foreground" />
                          {asset.owner}
                        </div>
                      </TableCell>
                      <TableCell>
                        <WarrantyBadge expiryDate={asset.warranty_expiry} />
                      </TableCell>
                      <TableCell><StatusBadge status={asset.status} /></TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button variant="ghost" size="icon" onClick={() => openEditDialog(asset)}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button 
                            variant="ghost" 
                            size="icon" 
                            onClick={() => handleDelete(asset)}
                            className="text-red-600 hover:text-red-700"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </ScrollArea>
        </CardContent>
      </Card>

      {/* Edit Dialog */}
      <Dialog open={isEditOpen} onOpenChange={setIsEditOpen}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>Edit Asset</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4 max-h-[60vh] overflow-y-auto">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Asset Name</Label>
                <Input
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>Asset Tag</Label>
                <Input
                  value={formData.asset_tag}
                  onChange={(e) => setFormData({ ...formData, asset_tag: e.target.value })}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Vendor</Label>
                <Input
                  value={formData.vendor}
                  onChange={(e) => setFormData({ ...formData, vendor: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>Model</Label>
                <Input
                  value={formData.model}
                  onChange={(e) => setFormData({ ...formData, model: e.target.value })}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Location</Label>
                <Input
                  value={formData.location}
                  onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>Owner</Label>
                <Input
                  value={formData.owner}
                  onChange={(e) => setFormData({ ...formData, owner: e.target.value })}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsEditOpen(false)}>Cancel</Button>
            <Button onClick={handleEdit}>Save Changes</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
