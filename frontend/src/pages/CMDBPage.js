import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';

export default function CMDBPage() {
    const [cis, setCis] = useState([]);
    const [loading, setLoading] = useState(true);
    const [filterCategory, setFilterCategory] = useState('');

    useEffect(() => {
        fetchCIs();
    }, [filterCategory]);

    const fetchCIs = async () => {
        try {
            const token = localStorage.getItem('token');
            const url = filterCategory ? `/api/cmdb/cis?category=${filterCategory}` : '/api/cmdb/cis';
            const response = await fetch(url, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) {
                const data = await response.json();
                setCis(data);
            }
        } catch (err) {
            console.error("Failed to fetch CIs", err);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight">Configuration Management Database (CMDB)</h1>
                    <p className="text-sm text-muted-foreground">Manage cloud and on-premises CIs, dependencies, and lifecycles.</p>
                </div>
            </div>

            <div className="flex gap-4">
                <Button variant={filterCategory === '' ? 'default' : 'outline'} onClick={() => setFilterCategory('')}>All Assets</Button>
                <Button variant={filterCategory === 'hardware' ? 'default' : 'outline'} onClick={() => setFilterCategory('hardware')}>Hardware</Button>
                <Button variant={filterCategory === 'virtual_machine' ? 'default' : 'outline'} onClick={() => setFilterCategory('virtual_machine')}>Virtual Machines</Button>
                <Button variant={filterCategory === 'software' ? 'default' : 'outline'} onClick={() => setFilterCategory('software')}>Software</Button>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>Configuration Items (CIs)</CardTitle>
                </CardHeader>
                <CardContent>
                    {loading ? (
                        <p>Loading inventory...</p>
                    ) : cis.length === 0 ? (
                        <p className="text-muted-foreground">No configuration items found.</p>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-left border-collapse">
                               <thead>
                                    <tr className="border-b text-sm text-muted-foreground">
                                        <th className="py-3 px-4">Name</th>
                                        <th className="py-3 px-4">Category</th>
                                        <th className="py-3 px-4">Environment</th>
                                        <th className="py-3 px-4">Provider</th>
                                        <th className="py-3 px-4">Status</th>
                                        <th className="py-3 px-4">Version</th>
                                    </tr>
                               </thead>
                               <tbody>
                                    {cis.map((ci) => (
                                        <tr key={ci.id} className="border-b hover:bg-muted/50 text-sm">
                                            <td className="py-3 px-4 font-medium">{ci.name}</td>
                                            <td className="py-3 px-4 capitalize">{ci.category}</td>
                                            <td className="py-3 px-4">
                                                <Badge variant="outline">{ci.environment}</Badge>
                                            </td>
                                            <td className="py-3 px-4">{ci.provider}</td>
                                            <td className="py-3 px-4">
                                                <Badge className={ci.status === 'active' ? 'bg-green-500 text-white' : 'bg-gray-400 text-white'}>
                                                    {ci.status}
                                                </Badge>
                                            </td>
                                            <td className="py-3 px-4">v{ci.version}</td>
                                        </tr>
                                    ))}
                               </tbody>
                            </table>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}