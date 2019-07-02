def test_segmentation_index(client):
    '''Start with a blank database.'''

    rv = client.get('/segmentation/index')
    print(rv.mimetype)
    print(rv.status_code)
    assert rv.mimetype == 'text/html'