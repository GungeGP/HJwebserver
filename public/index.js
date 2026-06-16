console.log("Hello from index.js!");

fetch('/api/data', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({ hello: "server" }) // This becomes request.body in Python!
})
    .then(response => response.json())
    .then(data => {
        console.log('Data from server:', data);
        const dataDiv = document.getElementById('data');
        dataDiv.textContent = JSON.stringify(data, null, 2);
    })
    .catch(error => { console.error('Error fetching data:', error); });